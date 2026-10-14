import re, json
TOKEN = re.compile(r'\s+|--[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_][\w]*|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|[{}\[\]=,;]')
class Node:
    def __init__(self, start, end, value=None, entries=None):
        self.start,self.end,self.value,self.entries=start,end,value,entries
class Lua:
    def __init__(self, text):
        self.text=text; self.tokens=[]; end=0
        for m in TOKEN.finditer(text):
            if text[end:m.start()].strip(): raise ValueError('Unsupported Lua data')
            end=m.end()
            if not m.group().isspace() and not m.group().startswith('--'): self.tokens.append((m.group(),m.start(),m.end()))
        if text[end:].strip(): raise ValueError('Unsupported Lua data')
        self.i=0; self.roots={}
        while self.i<len(self.tokens):
            key=self.take()[0]; self.expect('='); self.roots[key]=self.value()
    def take(self):
        t=self.tokens[self.i]; self.i+=1; return t
    def expect(self,x):
        if self.take()[0]!=x: raise ValueError('Invalid Lua structure')
    def value(self):
        t,s,e=self.take()
        if t=='{':
            entries={}; idx=1
            while self.tokens[self.i][0]!='}':
                if self.tokens[self.i][0]=='[':
                    self.take(); k=self.value().value; self.expect(']'); self.expect('=')
                elif self.i+1<len(self.tokens) and self.tokens[self.i+1][0]=='=':
                    k=self.take()[0]; self.expect('=')
                else: k=idx; idx+=1
                entries[k]=self.value()
                if self.tokens[self.i][0] in (',',';'): self.take()
            return Node(s,self.take()[2],entries=entries)
        if t.startswith(('"',"'")):
            v=re.sub(r'\\([0-9]{1,3}|.)', lambda m: chr(int(m[1])) if m[1].isdigit() else {'n':'\n','r':'\r','t':'\t'}.get(m[1],m[1]), t[1:-1])
        elif t in ('true','false','nil'): v={'true':True,'false':False,'nil':None}[t]
        else:
            try: v=float(t) if any(c in t for c in '.eE') else int(t)
            except ValueError: raise ValueError('Non-data Lua value: '+t)
        return Node(s,e,value=v)
    def raw(self,n): return self.text[n.start:n.end]

def table(n,key): return n.entries.get(key) if n and n.entries is not None else None

def edit(text, changes):
    for start,end,value in sorted(changes,reverse=True): text=text[:start]+value+text[end:]
    Lua(text)
    return text

def setkey(doc,node,key,raw,changes):
    old=table(node,key)
    if old: changes.append((old.start,old.end,raw))
    else: changes.append((node.end-1,node.end-1,'\n['+json.dumps(key)+'] = '+raw+',\n'))
