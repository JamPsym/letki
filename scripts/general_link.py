"""Versioned, binary-safe Letki transport and capability-aware driver."""
import ctypes
import fcntl
import glob
import json
import os
from pathlib import Path
import secrets
import select
import struct
import subprocess
import termios
import time
from uart_demo import SerialLink as RawSerial

ROOT = Path(__file__).resolve().parents[1]
HELLO, STATUS, TIME, BEGIN, WRITE, COMMIT, ABORT, PLAY, PAUSE, SEEK, FLUSH, BRIGHTNESS, FRAME_BEGIN, FRAME_DATA, FRAME_COMMIT, QUEUE, READ, BAUD_PREPARE, BAUD_CONFIRM = range(1, 20)
ERRORS = ('OK', 'INVALID', 'BUSY', 'SPACE', 'CRC', 'ORDER', 'UNSUPPORTED', 'IO', 'SESSION', 'CONFLICT')

class ProtocolError(RuntimeError):
    def __init__(self, node, op, status):
        self.node, self.op, self.status = node, op, status
        super().__init__(f'tile {node}: {ERRORS[status] if status < len(ERRORS) else status} on operation {op}')

def crc(data):
    value = 0xffff
    for byte in data:
        value ^= byte << 8
        for _ in range(8): value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 0xffff
    return value

def cobs(data):
    out = bytearray([0]); position = 0; code = 1
    for byte in data:
        if byte:
            out.append(byte); code += 1
        else:
            out[position] = code; position = len(out); out.append(0); code = 1
    out[position] = code
    return bytes(out) + b'\0'

def uncobs(data):
    out = bytearray(); index = 0
    while index < len(data):
        code = data[index]; index += 1
        if not code or index + code - 1 > len(data): raise ValueError('Invalid COBS')
        out.extend(data[index:index+code-1]); index += code-1
        if code != 255 and index < len(data): out.append(0)
    return bytes(out)

def packet(node, op, session, request, payload=b''):
    if len(payload) > 48: raise ValueError('Payload exceeds 48 bytes')
    body = struct.pack('<BBBHHB', 1, op, node, session, request, len(payload)) + payload
    return cobs(body + struct.pack('<H', crc(body)))

def unpack(wire):
    if not wire.endswith(b'\0') or len(wire)>60: raise ValueError('Invalid packet framing')
    data = uncobs(wire[:-1])
    if len(data)<10 or len(data)!=10+data[7] or crc(data[:-2])!=int.from_bytes(data[-2:], 'little'):
        raise ValueError('Invalid packet size/CRC')
    version, op, node, session, request, length = struct.unpack_from('<BBBHHB', data)
    if version != 1: raise ValueError('Unsupported protocol version')
    return node, op, session, request, data[8:8+length]

def library():
    path = ROOT/'build/general/libletki-general.so'
    if not path.exists(): raise RuntimeError('Run make general-test first')
    lib = ctypes.CDLL(str(path))
    lib.lg_sim_exchange.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint32]
    lib.lg_sim_exchange.restype = ctypes.c_uint
    lib.lg_sim_render.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint32]
    lib.lg_sim_source.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint]
    lib.lg_sim_create.restype = ctypes.c_void_p
    lib.lg_sim_reset.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.lg_sim_destroy.argtypes = [ctypes.c_void_p]
    lib.lg_sim_fault.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    lib.lg_sim_operations.argtypes = [ctypes.c_void_p]
    lib.lg_sim_render.restype = ctypes.POINTER(ctypes.c_uint8)
    lib.font_compact_column.argtypes = [ctypes.c_uint32, ctypes.c_uint8]
    lib.font_compact_column.restype = ctypes.c_uint8
    return lib

class Simulation:
    def __init__(self, erase=True):
        self.lib = library(); self.context = self.lib.lg_sim_create()
        if not self.context: raise MemoryError('Simulator allocation failed')
        self.now = 0; self.missing = set(); self.corrupt_once = False; self.drop_reply_once = False
        self.bytes = 0
    def exchange(self, messages, timeout=2):
        results = []
        for message in messages:
            self.bytes += len(message); wire = message
            if self.corrupt_once:
                self.corrupt_once = False; wire = wire[:-3]+bytes([wire[-3]^1])+wire[-2:]
            for node in range(5):
                if node in self.missing: continue
                data = ctypes.create_string_buffer(wire, 60)
                used = self.lib.lg_sim_exchange(self.context, node, data, len(wire)-1, self.now & 0xffffffff)
                if not used: wire = b''; break
                wire = data.raw[:used]
            if wire: results.append(wire)
        if self.drop_reply_once: self.drop_reply_once = False; return []
        return results
    def advance(self, ms):
        self.now += ms
        return self.pixels()
    def pixels(self):
        return [bytes(self.lib.lg_sim_render(self.context, i, self.now & 0xffffffff)[:64]) for i in range(5)]
    def set_source(self, program):
        buffer=ctypes.create_string_buffer(program)
        if not self.lib.lg_sim_source(self.context,buffer,len(program)):raise ValueError('Invalid host-source program')
        self.program_buffer=buffer
    def reboot(self): self.lib.lg_sim_reset(self.context, 0); self.now = 0
    def fault(self, after): self.lib.lg_sim_fault(self.context, after)
    def close(self):
        if self.context: self.lib.lg_sim_destroy(self.context); self.context = None
    def __del__(self):
        if getattr(self, 'context', None): self.close()

class Serial:
    def __init__(self, port=None):
        ports = glob.glob('/dev/serial/by-id/*WCH-Link*')
        port = port or (ports[0] if len(ports)==1 else None)
        if not port: raise RuntimeError('Specify --port /dev/ttyACM0')
        busy = subprocess.run(['fuser', str(Path(port).resolve())], capture_output=True)
        if busy.returncode == 0: raise RuntimeError('Close picocom or other serial readers before connecting.')
        self.raw = RawSerial(port); self.buffer = bytearray(); self.discard = False; self.port = port
        try:
            fcntl.flock(self.raw.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.ioctl(self.raw.fd, termios.TIOCEXCL)
        except Exception:
            self.raw.close(); raise
        self.baud = 115200
        self.diagnostics = dict(exchanges=0, timeouts=0, invalid_replies=0)
        self.raw._write(b"\0")
    def exchange(self, messages, timeout=2):
        expected={(n,s,q) for n,o,s,q,p in map(unpack,messages)}
        self.diagnostics['exchanges'] += 1
        for message in messages: self.raw._write(message)
        end = time.monotonic()+timeout; replies = []; seen=set()
        while len(replies) < len(messages):
            while 0 in self.buffer:
                raw, _, rest = self.buffer.partition(b'\0'); self.buffer = bytearray(rest)
                if self.discard:
                    self.discard = False
                    continue
                if raw:
                    try: n,o,s,q,p=unpack(bytes(raw)+b'\0')
                    except ValueError:
                        self.diagnostics['invalid_replies'] += 1
                        continue
                    key=n,s,q
                    if key in expected and key not in seen:
                        replies.append(bytes(raw)+b'\0');seen.add(key)
            # Bound only an unterminated tail. A USB read can contain several
            # complete responses, all of which must be parsed first.
            if len(self.buffer)>59:
                self.buffer.clear(); self.discard = True
            if len(replies)>=len(messages): break
            remaining = end-time.monotonic()
            if remaining<=0 or not select.select([self.raw.fd], [], [], remaining)[0]: break
            data = os.read(self.raw.fd, 256)
            if not data: raise EOFError('Serial disconnected')
            self.buffer.extend(data)
        if len(replies)<len(messages):
            self.diagnostics['timeouts'] += 1
            self.diagnostics['last_timeout'] = dict(missing=sorted(expected-seen),
                operations=[unpack(m)[1] for m in messages],buffer_hex=self.buffer.hex(),discard=self.discard)
        return replies
    def set_baud(self, rate):
        speed = getattr(termios, 'B'+str(rate))
        termios.tcdrain(self.raw.fd)
        settings = termios.tcgetattr(self.raw.fd); settings[4] = settings[5] = speed
        termios.tcsetattr(self.raw.fd, termios.TCSANOW, settings); self.baud = rate
    def close(self):
        try: fcntl.ioctl(self.raw.fd, termios.TIOCNXCL)
        finally: self.raw.close()

class Driver:
    def __init__(self, link, tiles=5):
        self.link = link; self.tiles = tiles; self.session = secrets.randbelow(65535)+1
        self.sequence = 0; self.sequences=[0]*tiles; self.clocks = {}; self.generation = 0; self.frame_deadlines=[]
        for attempt in range(3):
            try:
                self.capabilities=[self.info(i,HELLO) for i in range(tiles)]
                break
            except ProtocolError as error:
                if error.op!=HELLO or error.status not in (5,8,9) or attempt==2:raise
                self.session=secrets.randbelow(65535)+1;self.sequences=[0]*tiles
        self.synchronize()
    def now(self): return self.link.now if isinstance(self.link, Simulation) else round(time.monotonic()*1000)
    def batch(self, operations, retries=2, timeout=2):
        messages = []; expected = {}
        for node, op, data in operations:
            self.sequences[node]=(self.sequences[node]+1)&65535
            sequence=self.sequences[node];self.sequence=sequence
            key = node, op|128, self.session, sequence
            expected[key] = None; messages.append((key, packet(node, op, self.session, sequence, data)))
        # At most one outstanding request per node: retries use the device's
        # bounded last-result cache, even for flash writes and play commands.
        if len({key[0] for key, _ in messages}) != len(messages): raise ValueError('One outstanding request per tile')
        for attempt in range(retries+1):
            waiting = [message for key, message in messages if expected[key] is None]
            if not waiting: break
            for raw in self.link.exchange(waiting, timeout):
                try: node, op, session, seq, result = unpack(raw)
                except ValueError: continue
                key = node, op, session, seq
                if key in expected:
                    if not result: raise ValueError('Reply has no result status')
                    if result[0]: raise ProtocolError(node, op & 127, result[0])
                    expected[key] = result[1:]
                elif (node, op|128, session, seq) in expected:
                    raise RuntimeError(f'Tile {node} did not consume its request; check topology/firmware')
        if any(value is None for value in expected.values()): raise TimeoutError('Missing Letki replies after bounded retries')
        return [expected[key] for key, _ in messages]
    def request(self, node, op, data=b'', **kwargs): return self.batch([(node, op, data)], **kwargs)[0]
    def info(self, node, op=STATUS):
        p = self.request(node, op)
        if len(p)!=47: raise ValueError('Unsupported capability payload')
        ram, length, safe, large = struct.unpack_from('<HHHH', p, 4)
        clock, position = struct.unpack_from('<II', p, 12)
        return dict(node=p[1], tiles=p[2], queue_slots=p[3], ram=ram, program_bytes=length,
                    flash_safe=safe, flash_capacity=large, clock=clock, position=position,
                    paused=bool(p[20]&1),mode='frames' if p[20]&2 else 'timeline', storage=p[21], queued=p[22], uploading=bool(p[23]&1),switch_pending=bool(p[23]&2),
                    presented=int.from_bytes(p[24:26], 'little'), desired=int.from_bytes(p[26:28], 'little'),
                    late=int.from_bytes(p[28:32], 'little'), brightness=p[32], maintenance=bool(p[33]),
                    uid=p[34:42].hex() if op==HELLO else None,
                    uart_errors=int.from_bytes(p[34:38],'little') if op!=HELLO else None,
                    tx_dropped=int.from_bytes(p[38:42],'little') if op!=HELLO else None,
                    ram_free=int.from_bytes(p[42:44],'little'),arena_total=int.from_bytes(p[44:46],'little'),
                    queue_free=p[46],queue_stride=(int.from_bytes(p[44:46],'little')-ram)//p[3] if p[3] else 80)
    def synchronize(self, timeout=2, require_fresh=True, flush_on_jump=False):
        previous=self.clocks.copy()
        for node in range(self.tiles):
            observations=[];fresh=[];age=65535
            for attempt in range(12):
                before=self.now();reply=self.request(node,TIME,timeout=timeout);after=self.now()
                remote=int.from_bytes(reply[:4],'little');age=int.from_bytes(reply[8:10],'little')
                sample=(after-before,remote-(before+after)//2,age)
                observations.append(sample)
                if not require_fresh or age<=500:fresh.append(sample)
                if len(fresh)>=3:break
                if require_fresh and age>500:time.sleep(.025)
            rtt,offset,selected_age=min(fresh or observations)
            self.clocks[node]=dict(offset=offset,uncertainty_ms=(rtt+1)//2,clock_age_ms=selected_age)
        jumped=[]
        for node,old in previous.items():
            new=self.clocks[node]
            delta=(new['offset']-old['offset']+0x80000000)%0x100000000-0x80000000
            if abs(delta)>max(20,old['uncertainty_ms']+new['uncertainty_ms']+10):jumped.append(node)
        if flush_on_jump and jumped:self.all(FLUSH)
        return jumped
    def local_time(self, node, host_ms): return (host_ms+self.clocks[node]['offset']) & 0xffffffff
    def all(self, op, data=b''):
        result=self.batch([(i, op, data) for i in range(self.tiles)])
        if op in (FLUSH,PAUSE):self.frame_deadlines=[]
        if op==QUEUE:
            for capability in self.capabilities:
                capability['queue_slots']=data[0]
                capability['queue_stride']=80 if len(data)==1 else (24,48,80)[data[1]]
        return result
    def load(self, program, storage='auto', replace='safe', start_at=None):
        programs=[bytes(program)]*self.tiles if isinstance(program,(bytes,bytearray)) else list(map(bytes,program))
        if len(programs)!=self.tiles:raise ValueError('Provide one program per tile')
        infos = [self.info(i) for i in range(self.tiles)]
        for i,info in enumerate(infos):
            if info['switch_pending'] and replace=='safe':raise ProtocolError(i,BEGIN,2)
            if info['uploading'] or info['maintenance'] or info['switch_pending']:self.request(i,ABORT)
        infos = [self.info(i) for i in range(self.tiles)]
        if any(i['queued'] for i in infos):self.all(FLUSH)
        reusable=start_at is None and all(i['program_bytes']==len(p) and
                    (storage=='auto' or (storage=='ram' and i['storage']==0) or
                     (storage=='flash' and i['storage'] in (1,2))) for p,i in zip(programs,infos))
        if reusable and all(self.read(node)==p for node,p in enumerate(programs)):
            self.all(PAUSE);self.seek(0)
            return dict(storage='existing',reused=True,bytes_per_tile=[len(p) for p in programs],total_bytes=sum(map(len,programs)))
        if storage=='auto':
            fits = all(len(p)<=i['arena_total'] for p,i in zip(programs,infos))
            if fits and any(len(p)>i['ram'] for p,i in zip(programs,infos)):
                self.all(PAUSE);self.all(FLUSH);self.all(QUEUE,b'\0')
                infos=[self.info(i) for i in range(self.tiles)]
            storage = 'ram' if fits else 'flash'
        mode = 0 if storage=='ram' else 1 if replace=='safe' else 2
        for node,(p,i) in enumerate(zip(programs,infos)):
            maximum=i['ram'] if mode==0 else i['flash_safe'] if mode==1 else i['flash_capacity']
            if len(p)>maximum:raise ValueError(f'Tile {node}: program needs {len(p)} bytes; selected capacity is {maximum}')
        policy = 0 if replace=='safe' else 1
        started = []
        try:
            # Persistent operations are deliberately serialized: stopped flash
            # maintenance can stall a relay; no pipeline through busy writers.
            for node,p in enumerate(programs):
                self.request(node, BEGIN, struct.pack('<BBHH',mode,policy,len(p),crc(p)),timeout=5);started.append(node)
            for node,p in enumerate(programs):
                for offset in range(0,len(p),46): self.request(node, WRITE, struct.pack('<H',offset)+p[offset:offset+46])
            for node in range(self.tiles): self.request(node, COMMIT, b'' if start_at is None else struct.pack('<I',self.local_time(node,start_at)))
        except Exception:
            for node in started:
                try: self.request(node, ABORT, retries=0)
                except Exception: pass
            raise
        self.synchronize()
        return dict(storage=storage, mode=mode, bytes_per_tile=[len(p) for p in programs],total_bytes=sum(map(len,programs)))
    def read(self, node):
        length = self.info(node)['program_bytes']; data = bytearray()
        for at in range(0,length,47): data.extend(self.request(node, READ, struct.pack('<HB',at,min(47,length-at))))
        return bytes(data)
    def play(self, position=0, loop=None, lead=250, allow_unsynced=False):
        stale=[i for i,c in self.clocks.items() if c['clock_age_ms']>500]
        if stale and not allow_unsynced:raise RuntimeError(f'Stale I2C clock on tiles {stale}; check SDA/SCL before standalone playback')
        loops=[bool(self.request(i,READ,struct.pack('<HB',0,8))[7]&1) if loop is None else bool(loop) for i in range(self.tiles)]
        self.all(FLUSH); deadline = self.now()+lead
        self.batch([(i,PLAY,struct.pack('<IIB',self.local_time(i,deadline),position,int(loops[i]))) for i in range(self.tiles)])
        return deadline
    def seek(self, position): self.all(FLUSH); self.all(SEEK,struct.pack('<I',position))
    def frame(self, pixels, when, fmt='gray4'):
        margin=0 if isinstance(self.link,Simulation) else max(v['uncertainty_ms'] for v in self.clocks.values())+5
        self.frame_deadlines=[t for t in self.frame_deadlines if t>self.now()-margin]
        if len(self.frame_deadlines)>=min(c['queue_slots'] for c in self.capabilities):
            raise ProtocolError(0,FRAME_BEGIN,2)
        formats = dict(mono1=0,gray4=1,level8=2); kind=formats[fmt]
        if any(c['queue_stride']<10+(8,32,64)[kind] for c in self.capabilities):raise ValueError('Configure queue slots large enough for this pixel format')
        if len(pixels)!=self.tiles: raise ValueError('A frame must include every tile')
        self.generation=(self.generation+1)&65535
        generation=struct.pack('<H',self.generation); packed=[]
        for tile in pixels:
            if len(tile)!=64 or any(not 0<=v<=100 for v in tile): raise ValueError('Expected 64 row-major levels 0..100 per tile')
            if kind==0:
                data=bytes(sum((1<<b) if tile[j+b] else 0 for b in range(8)) for j in range(0,64,8))
            elif kind==1:
                q=[(v*15+50)//100 for v in tile];data=bytes(q[j]|q[j+1]<<4 for j in range(0,64,2))
            else: data=bytes(tile)
            packed.append(data)
        try:
            # A lost acknowledgement must not consume the two-second control
            # timeout while already queued frames run out. The largest batch
            # takes <100ms on a healthy 115200 five-tile chain; keep retry time
            # bounded while retaining its cache. Multiple losses or an explicitly
            # forced high FPS can still exhaust lookahead; report skips/lateness.
            self.batch([(i,FRAME_BEGIN,generation+struct.pack('<IB',self.local_time(i,when),kind)+data[:41]) for i,data in enumerate(packed)],timeout=.25)
            for offset in range(41,max(map(len,packed)),45):
                self.batch([(i,FRAME_DATA,generation+bytes([offset])+data[offset:offset+45]) for i,data in enumerate(packed) if offset<len(data)],timeout=.25)
            self.batch([(i,FRAME_COMMIT,generation) for i in range(self.tiles)],timeout=.25)
        except Exception:
            try: self.all(FLUSH)
            except Exception: pass
            self.frame_deadlines=[]
            raise
        self.frame_deadlines.append(when)
        return self.generation
    def close(self):
        try:
            if isinstance(self.link,Serial) and self.link.baud!=115200:self.set_baud(115200)
        finally:self.link.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def set_baud(self, baud):
        if not isinstance(self.link, Serial): raise RuntimeError('Baud switching requires a physical serial link')
        if baud not in (115200,230400,460800,921600): raise ValueError('Unsupported baud')
        try:
            self.all(BAUD_PREPARE,struct.pack('<H',baud//100))
            time.sleep(1.15); self.link.set_baud(baud)
            self.all(BAUD_CONFIRM); self.synchronize()
        except Exception:
            # Some nodes may never have received PREPARE and still hold a
            # confirmed high-rate lease. Wait for both recovery paths.
            time.sleep(10.5); self.link.set_baud(115200)
            raise

class TimedSimulation(Simulation):
    """UART serialization model, not a physical throughput qualification.
    Each complete frame traverses six wires and five store/forward processors.
    The C firmware core handles every request at its modeled arrival time.
    """
    def __init__(self, baud=115200, processing_ms=.05):
        super().__init__();self.baud=baud;self.processing_ms=processing_ms
        self.links=[0.0]*6;self.elapsed=0.0
    def exchange(self, messages, timeout=2):
        results=[];finished=self.elapsed
        for message in messages:
            self.bytes+=len(message);wire=message
            at=max(self.elapsed,self.links[0])+len(wire)*10000/self.baud;self.links[0]=at
            for node in range(5):
                self.lib.lg_sim_render(self.context,node,round(at)&0xffffffff)
                if node not in self.missing:
                    data=ctypes.create_string_buffer(wire,60)
                    used=self.lib.lg_sim_exchange(self.context,node,data,len(wire)-1,round(at)&0xffffffff)
                    if not used:wire=b'';break
                    wire=data.raw[:used]
                at=max(at+self.processing_ms,self.links[node+1])+len(wire)*10000/self.baud
                self.links[node+1]=at
            if wire:results.append(wire)
            finished=max(finished,at)
        self.elapsed=finished;self.now=round(finished);self.pixels()
        return results
    def advance(self, ms):
        self.elapsed+=ms;self.now=round(self.elapsed);return self.pixels()
