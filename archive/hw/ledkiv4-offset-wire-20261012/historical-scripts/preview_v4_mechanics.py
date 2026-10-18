#!/usr/bin/env python3
"""Render the actual FreeCAD prototype solids as assembly illustrations."""
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'build/hardware/v4/mechanical'
os.environ.setdefault('MPLCONFIGDIR',str(OUTPUT/'.matplotlib'))
sys.path.append('/usr/lib/freecad/lib')
import FreeCAD as App
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def draw(ax,shape,colour,alpha=1,offset=0,outlines=False):
    vertices,triangles=shape.tessellate(.12)
    faces=[[(vertices[i].x,vertices[i].y,vertices[i].z+offset) for i in tri] for tri in triangles]
    ax.add_collection3d(Poly3DCollection(faces,facecolors=colour,edgecolors=colour,
                                      linewidths=.1,alpha=alpha))
    if outlines:
        for edge in shape.Edges:
            points=edge.discretize(12)
            ax.plot([p.x for p in points],[p.y for p in points],
                    [p.z+offset for p in points],color='#90939c',linewidth=.45)


def main():
    one=App.openDocument(str(OUTPUT/'letkiv4-mechanics-1-tiles.FCStd'))
    figure=plt.figure(figsize=(11,8),facecolor='#f7f7f4')
    ax=figure.add_subplot(111,projection='3d',computed_zorder=False)
    ax.set_position((.03,.12,.66,.78))
    for name,colour,offset,alpha in [('Carrier','#485462',0,1),('PCB1','#3a8c63',0,1),
        ('OpaqueGrid1','#35363b',13,1),('TranslucentFace1','#e4e3d2',27,.65),
        ('FrontBezel1','#35363b',40,1)]:
        draw(ax,one.getObject(name).Shape,colour,alpha,offset,outlines=name=='OpaqueGrid1')
    for label,y in [('Rear carrier',.25),('PCB',.35),('Grid: walls seat on PCB',.48),
                    ('Translucent face',.63),('Bezel and top hooks',.75)]:
        figure.text(.70,y,label,fontsize=10,color='#343b44')
    ax.set(xlim=(-3,44),ylim=(-4,60),zlim=(-11,51))
    ax.set_box_aspect((47,64,62));ax.view_init(elev=34,azim=-66);ax.set_axis_off()
    figure.suptitle('Letki v4 — removable optical assembly',fontsize=17,x=.5,y=.94)
    figure.text(.5,.055,'Exploded nominal CAD • two M2 mounting screws • unprinted prototype',ha='center',fontsize=11,color='#59616b')
    figure.savefig(OUTPUT/'assembly-exploded.png',dpi=170,bbox_inches='tight',facecolor=figure.get_facecolor())
    plt.close(figure)
    four=App.openDocument(str(OUTPUT/'letkiv4-mechanics-4-tiles.FCStd'))
    figure=plt.figure(figsize=(13,6),facecolor='#f7f7f4')
    ax=figure.add_subplot(111,projection='3d',computed_zorder=False)
    draw(ax,four.getObject('Carrier').Shape,'#485462')
    for tile in range(1,5):draw(ax,four.getObject('PCB'+str(tile)).Shape,'#82b698',.28)
    for obj in four.Objects:
        if obj.Name.startswith('WireBridge'):draw(ax,obj.Shape,'#b4adb0')
        elif obj.Name.startswith('TP') and hasattr(obj,'Shape'):draw(ax,obj.Shape,'#d8a33e')
    for name in ('SpliceTop','SpliceBottom'):draw(ax,four.getObject(name).Shape,'#e4a34b')
    ax.set(xlim=(-3,177),ylim=(-5,60),zlim=(-13,1))
    ax.set_box_aspect((180,65,14));ax.view_init(elev=-38,azim=-69);ax.set_axis_off()
    figure.suptitle('Letki v4 — four-board rear carrier',fontsize=17,x=.5,y=.95)
    figure.text(.5,.05,'162.56 × 57.27 mm • staple bridges and probe access • cable windows • splice plates at section ends',ha='center',fontsize=11,color='#59616b')
    figure.savefig(OUTPUT/'carrier-rear.png',dpi=170,bbox_inches='tight',facecolor=figure.get_facecolor())
    print('Rendered assembly-exploded.png and carrier-rear.png from the FreeCAD solids.')


if __name__=='__main__':main()
