#!/usr/bin/env python3
"""Freeze already-built general firmware and emit its memory/review manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix',default=str(ROOT/'.tools/mrs-1.90/RISC-V_Embedded_GCC/bin/riscv-none-embed-'))
    args=parser.parse_args();out=ROOT/'build/general/review-candidate';out.mkdir(parents=True,exist_ok=True)
    roles={}
    for role in ('head','tile1','tile2','tile3','tile4'):
        build=ROOT/f'build/v3-general-{role}';elf=build/'letki.elf';image=(build/'letki.bin').read_bytes()
        fields=subprocess.check_output([args.prefix+'size',str(elf)],text=True).splitlines()[1].split()
        text,data,bss=map(int,fields[:3]);symbols={}
        for line in subprocess.check_output([args.prefix+'nm','-n',str(elf)],text=True).splitlines():
            values=line.split()
            if len(values)==3:symbols[values[2]]=int(values[0],16)
        start,end=symbols['__content_start'],symbols['__content_end'];pool=end-start
        assert start%64==0 and start-0x08000000>=len(image) and pool>=128
        assert data+bss<=2048 and symbols['__stack_size']==256
        record=dict(image_bytes=len(image),sha256=hashlib.sha256(image).hexdigest(),ram_including_stack=data+bss,
                    ram_free=2048-data-bss,stack_reserved=256,content_start=hex(start),content_bytes=pool,
                    flash_safe_program_bytes=(pool//128)*64-64,flash_capacity_program_bytes=pool-64)
        roles[role]=record;destination=out/role;destination.mkdir(exist_ok=True)
        for extension in ('bin','elf','hex','map'):shutil.copyfile(build/f'letki.{extension}',destination/f'letki.{extension}')
    source_paths=[ROOT/'Makefile',ROOT/'host/general/Makefile',ROOT/'host/general/sim.c',ROOT/'host/pwm-show/pwm_show.c',ROOT/'host/pwm-show/pwm_show.h',ROOT/'host/renderer/model.c',ROOT/'host/renderer/main.c',ROOT/'docs/general-firmware-protocol.txt']
    source_paths+=sorted((ROOT/'firmware/general').rglob('*'))
    source_paths+=[ROOT/'firmware/v3/User'/name for name in ('uart.c','uart.h','display.c','display.h')]
    source_paths+=[ROOT/'scripts'/name for name in ('general_link.py','general_program.py','general_audio.py','letki_general.py','general_resources.py','pwm_board_audio.py')]
    source_paths+=sorted((ROOT/'tests').glob('test_general*'))
    source_paths+=sorted((ROOT/'tests/mock_general_clock').glob('*'))
    source_paths+=sorted((ROOT/'config/general').glob('*'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths if p.is_file()}
    usage={}
    for source in (ROOT/'build/v3-general-head').rglob('*.su'):
        for line in source.read_text().splitlines():
            name,amount,kind=line.split('\t');usage[name.rsplit(':',1)[-1]]=int(amount)
    path={name:usage[name] for name in ('main','lg_receive','lg_dispatch','manifest','lg_program_valid')}
    foreground=sum(path.values());assert foreground+48<=256
    report=dict(status='BUILD_SNAPSHOT_ASTRA_REVIEW_RECORDED_SEPARATELY',roles=roles,ram_arena_total=752,
                default_program_ram=592,queue_stride_bytes=dict(mono1=24,gray4=48,level8=80),queue_max_slots=16,
                stack=dict(foreground_path=path,foreground_bytes=foreground,conservative_ISR_allowance=48,
                           conservative_total=foreground+48,runtime_high_water_measured=False),
                physical_validation=False,source_sha256=hashes,
                notes=['All capacities above come from native builds; simulator flash defaults to 4096 bytes.',
                       'This is a preflash build manifest; physical results are recorded separately.',
                       'Astra review and its resolution are recorded in docs/general-firmware-review-20261017.txt.'])
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({role:roles[role] for role in ('head','tile4')},indent=2))
if __name__=='__main__':main()
