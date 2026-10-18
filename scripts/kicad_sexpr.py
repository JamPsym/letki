"""Small KiCad S-expression reader/writer for explicit source transformations."""
import json
import re
from pathlib import Path

class Quoted(str): pass

def parse(text):
    tokens = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', text)
    stack = []; root = None
    for token in tokens:
        if token == '(':
            node = []
            if stack: stack[-1].append(node)
            else:
                if root is not None: raise ValueError('Multiple roots')
                root = node
            stack.append(node)
        elif token == ')':
            if not stack: raise ValueError('Unexpected closing parenthesis')
            stack.pop()
        else:
            if not stack: raise ValueError('Atom outside root')
            stack[-1].append(Quoted(json.loads(token)) if token.startswith('"') else token)
    if stack or root is None: raise ValueError('Incomplete S-expression')
    return root

def read(path): return parse(Path(path).read_text())
def children(node, tag): return [n for n in node if isinstance(n,list) and n and n[0]==tag]
def child(node, tag): return next(iter(children(node,tag)),None)
def prop(node,name): return next((n for n in children(node,'property') if n[1]==name),None)
def atom(value): return json.dumps(str(value),ensure_ascii=False) if isinstance(value,Quoted) else str(value)
def dumps(node, depth=0):
    prefix='\t'*depth
    if all(not isinstance(v,list) for v in node): return prefix+'('+ ' '.join(atom(v) for v in node)+')'
    scalars=[];nested=[]
    for value in node:
        if isinstance(value,list): nested.append(dumps(value,depth+1))
        else: scalars.append(atom(value))
    return prefix+'('+' '.join(scalars)+'\n'+'\n'.join(nested)+'\n'+prefix+')'
def write(path,node): Path(path).write_text(dumps(node)+'\n')
