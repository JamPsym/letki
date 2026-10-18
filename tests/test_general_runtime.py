import ctypes
import json
from pathlib import Path
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from general_link import *
from general_program import compile_show, text_show

class RuntimeTest(unittest.TestCase):
    def setUp(self):self.sim=Simulation();self.driver=Driver(self.sim)
    def tearDown(self):self.sim.close()
    def test_stream_retries_fit_lookahead_and_preserve_staged_frame(self):
        exchange=self.sim.exchange;lost=set()
        def drop_stage(messages,timeout=2):
            replies=exchange(messages,timeout)
            op=unpack(messages[0])[1]
            if op in (TIME,FRAME_BEGIN,FRAME_DATA,FRAME_COMMIT) and op not in lost:
                lost.add(op);self.sim.now+=round(timeout*1000)
                return []
            return replies
        self.sim.exchange=drop_stage
        self.driver.synchronize(timeout=.1)
        self.assertTrue(all(c['offset']==0 for c in self.driver.clocks.values()))
        self.driver.frame([bytes([50])*64]*5,1000,'level8')
        self.assertEqual(lost,{TIME,FRAME_BEGIN,FRAME_DATA,FRAME_COMMIT})
        self.assertLess(self.sim.now,1000)
        self.assertEqual(self.sim.advance(1000-self.sim.now),[bytes([50])*64]*5)
        self.assertTrue(all(self.driver.info(i)['late']==0 for i in range(5)))
    def test_uart_stream_clock_samples_do_not_wait_for_i2c_and_flush_jumps(self):
        from unittest.mock import patch
        exchange=self.sim.exchange;shift=[0];requests=[0]
        def clock_replies(messages,timeout=2):
            replies=exchange(messages,timeout);result=[]
            for reply in replies:
                node,op,session,seq,payload=unpack(reply)
                if op==(TIME|128):
                    requests[0]+=1;data=bytearray(payload)
                    data[1:5]=struct.pack('<I',(int.from_bytes(data[1:5],'little')+shift[0])&0xffffffff)
                    data[-2:]=b'\xff\xff'
                    reply=packet(node,op,session,seq,data)
                result.append(reply)
            return result
        self.sim.exchange=clock_replies
        self.driver.frame([bytes([50])*64]*5,1000)
        with patch('general_link.time.sleep',side_effect=AssertionError('Freshness wait in UART-only stream')):
            self.assertEqual(self.driver.synchronize(timeout=.1,require_fresh=False,flush_on_jump=True),[])
        self.assertEqual(requests[0],15)
        self.assertTrue(all(c['clock_age_ms']==65535 for c in self.driver.clocks.values()))
        self.assertTrue(all(self.driver.info(i)['queued']==1 for i in range(5)))
        shift[0]=500
        self.assertEqual(self.driver.synchronize(timeout=.1,require_fresh=False,flush_on_jump=True),list(range(5)))
        self.assertFalse(self.driver.frame_deadlines)
        self.assertTrue(all(self.driver.info(i)['queued']==0 for i in range(5)))
        self.driver.frame([bytes([80])*64]*5,1000)
        self.assertEqual(self.sim.advance(1500),[bytes([80])*64]*5)
    def test_play_while_loading_then_switch_at_deadline(self):
        first=compile_show(dict(duration_ms=1000,tracks=[dict(type='fill',motion='linear',period_ms=1000,levels=[0,100])]))
        second=compile_show(dict(duration_ms=1000,tracks=[dict(type='fill',levels=[80,80])]))
        self.driver.load(first);self.driver.play(lead=0)
        self.assertEqual(self.sim.advance(100)[0],bytes([10])*64)
        self.driver.load(second,start_at=500)
        self.assertEqual(self.sim.advance(200)[0],bytes([30])*64)
        self.assertEqual(self.sim.advance(200)[0],bytes([80])*64)
        self.assertEqual(self.driver.read(0),second)
    def test_automatic_ram_reclaim_and_per_node_memory_reports(self):
        program=bytearray(compile_show(dict(duration_ms=100,tracks=[])))
        program.extend(bytes(700-len(program)));program[4:6]=struct.pack('<H',700)
        report=self.driver.load(program)
        self.assertEqual(report['storage'],'ram')
        info=self.driver.info(0)
        self.assertEqual(info['ram'],752);self.assertEqual(info['ram_free'],52);self.assertEqual(info['queue_slots'],0)
    def test_short_program_can_have_multi_hour_duration(self):
        show=dict(duration_ms=10800000,tracks=[dict(type='fill',duration_ms=10800000,levels=[40,40])])
        self.driver.load(compile_show(show));self.driver.play(lead=0)
        for now in range(0,10800000,12345):
            self.sim.now=now;self.assertEqual(self.sim.pixels()[4],bytes([40])*64)
    def test_hour_of_real_time_frames_has_constant_queue_memory(self):
        self.driver.all(QUEUE,b'\x06')
        before=self.driver.info(0)['ram']
        for second in range(3600):
            pixels=[bytes([second%101])*64]*5
            self.driver.frame(pixels,self.sim.now+100,'gray4')
            rendered=self.sim.advance(100)
            expected=((second%101*15+50)//100)*100//15
            self.assertEqual(rendered[3],bytes([expected])*64)
            self.sim.advance(900)
        self.assertEqual(self.driver.info(0)['ram'],before)
        self.assertEqual(self.driver.info(0)['queued'],0)
    def test_binary_router_flags_overflow_timeout_and_resynchronization(self):
        lib=self.sim.lib
        lib.lg_sim_byte.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint32]
        lib.lg_sim_output.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p]
        def send(data,now=0):
            for value in data:lib.lg_sim_byte(self.sim.context,0,value,now)
            output=ctypes.create_string_buffer(60)
            length=lib.lg_sim_output(self.sim.context,0,output)
            return output.raw[:length]
        request=packet(0,BRIGHTNESS,self.driver.session,self.driver.sequences[0]+1,b'\x13')
        for flag in (0x100,0x200):
            self.assertFalse(send([request[0]|flag]+list(request[1:])))
        self.assertFalse(send([1]*120+[0]))
        self.assertFalse(send(request[:3],0));self.assertFalse(send(request[3:],300))
        self.assertEqual(unpack(send(request,301))[-1],b'\0')
        self.driver.sequences[0]+=1
        self.assertEqual(self.driver.info(0)['brightness'],19)
    def test_every_supported_text_mode_and_invalid_utf8_boundary(self):
        for mode in ('scroll','bounce','fall'):
            show=text_show('ZAŻÓŁĆ GĘŚLĄ JAŹŃ 123!',mode)
            self.driver.load(compile_show(show),replace='capacity');self.driver.play(lead=0)
            states=set();base=self.sim.now
            for offset in range(0,show['duration_ms'],100):
                self.sim.now=base+offset;states.add(b''.join(self.sim.pixels()))
            self.assertGreater(len(states),2)
        with self.assertRaises(ValueError):text_show('\ud800')
    def test_malformed_tracks_are_rejected_before_committing(self):
        lib=self.sim.lib;lib.lg_program_valid.argtypes=[ctypes.c_void_p,ctypes.c_uint]
        program=compile_show(ROOT/'config/general/demo.json')
        self.assertTrue(lib.lg_program_valid(ctypes.create_string_buffer(program),len(program)))
        for offset,value in [(6,17),(7,2),(16,99),(18,255),(19,1),(32,0),(36,0),(46,101)]:
            bad=bytearray(program);bad[offset]=value
            self.assertFalse(lib.lg_program_valid(ctypes.create_string_buffer(bytes(bad)),len(bad)),offset)
    def test_baud_switch_idle_gate_confirmation_lease_and_recovery(self):
        lib=self.sim.lib
        lib.lg_sim_rate.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint]
        poll=lambda now,idle=1:lib.lg_sim_rate(self.sim.context,0,now,idle)
        self.driver.request(0,BAUD_PREPARE,struct.pack('<H',4608))
        self.assertEqual(poll(999),0);self.assertEqual(poll(1000,0),0)
        self.assertEqual(poll(1000),460800)
        self.sim.now=1100;self.driver.request(0,BAUD_CONFIRM)
        self.assertEqual(poll(3001),0)
        self.assertEqual(poll(11100),115200)
        self.sim.now=12000;self.driver.request(0,BAUD_PREPARE,struct.pack('<H',2304))
        self.assertEqual(poll(13000),230400)
        self.assertEqual(poll(15000),115200)
    def test_reconnect_can_abort_an_incomplete_load_and_recover(self):
        program=compile_show(dict(duration_ms=1000,tracks=[]))
        self.driver.request(0,BEGIN,struct.pack('<BBHH',0,0,len(program),crc(program)))
        self.driver.request(0,WRITE,b'\0\0'+program[:5])
        second=Driver(self.sim)
        self.assertTrue(second.info(0)['uploading'])
        second.load(program)
        self.assertEqual(second.read(0),program)
    def test_pause_cancels_future_frames_and_stale_deadlines_reject(self):
        self.driver.frame([bytes([100])*64]*5,100)
        self.driver.all(PAUSE)
        self.assertEqual(self.sim.advance(100)[0],bytes(64))
        with self.assertRaises(ProtocolError):
            self.driver.request(0,FRAME_BEGIN,struct.pack('<HIB',1,self.sim.now+60001,0))

    def test_format_aware_queue_uses_available_memory_and_enforces_bounds(self):
        for fmt,stride in ((0,24),(1,48),(2,80)):
            self.driver.all(FLUSH);slots=min(16,752//stride)
            self.driver.all(QUEUE,bytes([slots,fmt]))
            info=self.driver.info(0)
            self.assertEqual(info['ram'],752-slots*stride)
            self.assertEqual(info['queue_stride'],stride)
        self.driver.all(QUEUE,bytes([16,0]))
        with self.assertRaises(ValueError):self.driver.frame([bytes(64)]*5,100,'gray4')
        with self.assertRaises(ProtocolError):self.driver.request(0,QUEUE,bytes([16,2]))
    def test_cross_page_flash_replacement_power_loss_in_both_policies(self):
        old=compile_show(ROOT/'config/general/demo.json')
        new=bytearray(old);new[46]=new[47]=20;new=bytes(new)
        for mode,policy in ((1,0),(2,1)):
            # Every erase page and every programmed byte, through all four
            # data pages and the final validity manifest.
            operations=(32 if mode==1 else 64)+320
            for cut in range(operations+1):
                self.sim.close();self.sim=Simulation();self.driver=Driver(self.sim)
                def upload(program,storage=1,replacement=0):
                    self.driver.request(0,BEGIN,struct.pack('<BBHH',storage,replacement,len(program),crc(program)))
                    for at in range(0,len(program),46):self.driver.request(0,WRITE,struct.pack('<H',at)+program[at:at+46])
                    self.driver.request(0,COMMIT)
                upload(old);self.sim.fault(cut)
                try:upload(new,mode,policy)
                except ProtocolError:pass
                self.sim.reboot();self.driver=Driver(self.sim)
                self.assertIn(self.driver.read(0),(old,new) if mode==1 else (b'',old,new))

    def test_independent_programs_utilize_each_tile_memory(self):
        programs=[compile_show(dict(duration_ms=1000,tracks=[dict(type='fill',levels=[i*20,i*20])])) for i in range(5)]
        self.driver.load(programs);self.driver.play(lead=0)
        for i,pixels in enumerate(self.sim.advance(100)):
            self.assertEqual(pixels,bytes([i*20])*64)
            self.assertEqual(self.driver.read(i),programs[i])

    def test_request_and_frame_identifiers_wrap_without_stopping_playback(self):
        self.driver.session=123
        wire=packet(0,HELLO,123,65534)
        self.sim.exchange([wire]);self.driver.sequences[0]=65534
        self.driver.request(0,TIME);self.driver.request(0,TIME)
        self.assertEqual(self.driver.sequences[0],0)
        self.driver=Driver(self.sim);self.driver.generation=65534
        self.assertEqual(self.driver.frame([bytes(64)]*5,100),65535)
        self.sim.advance(100)
        self.assertEqual(self.driver.frame([bytes([100])*64]*5,200),0)
        self.sim.advance(100);info=self.driver.info(0)
        self.assertEqual(info['presented'],0);self.assertEqual(info['mode'],'frames')

    def test_random_session_collision_renegotiates_without_resetting_playback(self):
        from unittest.mock import patch
        program=compile_show(dict(duration_ms=1000,tracks=[dict(type='fill',levels=[50,50])]))
        self.driver.load(program);self.driver.play(lead=0);self.sim.advance(100)
        current=self.driver.session;next_session=(current%65535)+1
        with patch('general_link.secrets.randbelow',side_effect=[current-1,next_session-1]):
            second=Driver(self.sim)
        self.assertEqual(second.session,next_session)
        self.assertEqual(second.read(0),program)
        self.assertEqual(self.sim.advance(100)[0],bytes([50])*64)

    def test_reload_identical_show_reuses_ram_and_avoids_flash_erase_wear(self):
        program=compile_show(ROOT/'config/general/narrated.json')
        self.driver.load(program)
        self.assertTrue(self.driver.load(program)['reused'])
        self.driver.load(program,storage='flash',replace='capacity')
        operations=self.sim.lib.lg_sim_operations(self.sim.context)
        self.assertTrue(self.driver.load(program,storage='flash')['reused'])
        self.assertEqual(self.sim.lib.lg_sim_operations(self.sim.context),operations)
    def test_play_default_uses_the_uploaded_program_loop_flag(self):
        program=compile_show(dict(duration_ms=1000,loop=False,tracks=[dict(type='fill',motion='linear',period_ms=1000,levels=[0,100])]))
        self.driver.load(program);self.driver.play(lead=0)
        self.assertEqual(self.sim.advance(1500)[0],bytes([99])*64)

    def test_continuous_show_survives_months_and_millisecond_clock_wrap(self):
        show=dict(duration_ms=60000,tracks=[dict(type='fill',motion='triangle',period_ms=60000,levels=[0,100])])
        self.driver.load(compile_show(show));self.driver.play(lead=0)
        for hour in range(4800):
            now=hour*3600123;self.sim.now=now
            phase=(now%60000)*1000//60000
            fraction=phase*2 if phase<=500 else (1000-phase)*2
            expected=100*fraction//1000
            self.assertEqual(self.sim.pixels()[0],bytes([expected])*64,hour)

    def test_pause_cancels_an_armed_segment_and_unfinished_load(self):
        old=compile_show(dict(duration_ms=1000,tracks=[dict(type='fill',levels=[25,25])]))
        new=compile_show(dict(duration_ms=1000,tracks=[dict(type='fill',levels=[80,80])]))
        self.driver.load(old);self.driver.play(lead=0);self.sim.advance(100)
        self.driver.load(new,start_at=500);self.driver.all(PAUSE)
        self.assertEqual(self.sim.advance(1000)[0],bytes([25])*64)
        self.assertFalse(self.driver.info(0)['switch_pending'])
        self.driver.request(0,BEGIN,struct.pack('<BBHH',0,0,len(new),crc(new)))
        self.driver.all(PAUSE)
        self.assertFalse(self.driver.info(0)['uploading'])
        self.assertEqual(self.driver.read(0),old)

    def test_pc_streaming_source_is_not_limited_by_mcu_program_storage(self):
        show=dict(duration_ms=1000,tracks=[dict(type='bitmap',pixels=[[100 if x%2 else 0 for x in range(500)] for y in range(8)])])
        program=compile_show(show);self.assertGreater(len(program),4032)
        source=Simulation()
        try:
            source.set_source(program);pixels=source.pixels()
            self.driver.frame(pixels,100,'gray4');self.sim.advance(100)
            self.assertEqual(self.sim.pixels(),pixels)
        finally:source.close()

    def test_original_pwm_show_can_stream_without_show_specific_device_code(self):
        from general_program import pwm_pixels
        seen=set();scenes=[set() for _ in range(6)]
        for milliseconds in range(0,38400,400):
            pixels=pwm_pixels(milliseconds)
            self.assertEqual(len(pixels),5);self.assertTrue(all(len(tile)==64 for tile in pixels))
            self.assertTrue(all(0<=v<=100 for tile in pixels for v in tile))
            self.driver.frame(pixels,self.sim.now+100,'gray4')
            self.sim.advance(100);image=b''.join(self.sim.pixels());seen.add(image);scenes[milliseconds//6400].add(image);self.sim.advance(300)
        self.assertGreater(len(seen),60)
        self.assertTrue(all(len(scene)>=4 for scene in scenes))

    def test_direct_uart_store_forward_model_at_each_rate(self):
        results=[]
        for baud in (115200,230400,460800,921600):
            sim=TimedSimulation(baud);driver=Driver(sim)
            try:
                driver.all(QUEUE,b'\x06');start=sim.now;costs=[]
                for frame in range(100):
                    begin=sim.now;driver.frame([bytes([frame%101])*64]*5,sim.now+200)
                    costs.append(sim.now-begin);sim.advance(200)
                results.append(dict(baud=baud,mean_transfer_ms=sum(costs)/len(costs),max_transfer_ms=max(costs)))
            finally:sim.close()
        out=ROOT/'build/general';out.mkdir(parents=True,exist_ok=True)
        (out/'transport-model.json').write_text(json.dumps(dict(kind='Serialization model; not physical qualification',results=results),indent=2)+'\n')
        self.assertGreater(results[0]['mean_transfer_ms'],results[-1]['mean_transfer_ms'])
        self.assertLess(results[2]['max_transfer_ms'],40)

if __name__=='__main__':unittest.main()
