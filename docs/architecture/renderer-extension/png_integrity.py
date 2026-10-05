"""PNG completion gate: chunk boundaries/CRCs/IEND and full pixel decoding."""
from pathlib import Path
from io import BytesIO
import hashlib, struct, zlib, os, tempfile
from PIL import Image

def inspect_png(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('Invalid PNG signature')
    offset=8; chunks=[]; ended=False
    while offset<len(data):
        if offset+12>len(data): raise ValueError('Truncated PNG chunk header')
        length=struct.unpack('>I',data[offset:offset+4])[0]
        tag=data[offset+4:offset+8]; end=offset+12+length
        if end>len(data): raise ValueError(f'Truncated {tag!r} chunk')
        payload=data[offset+8:offset+8+length]
        crc=struct.unpack('>I',data[offset+8+length:end])[0]
        if zlib.crc32(tag+payload)&0xffffffff!=crc: raise ValueError(f'Bad {tag!r} CRC')
        chunks.append({'type':tag.decode('ascii'),'bytes':length}); offset=end
        if tag==b'IEND':
            if length:raise ValueError('IEND payload must be empty')
            ended=True;break
    if not ended or offset!=len(data):raise ValueError('Missing IEND or trailing data')
    with Image.open(BytesIO(data))as im: im.verify()
    with Image.open(BytesIO(data))as im:
        im.load(); size=im.size
        # Decode final row too; an intact header is not sufficient.
        bottom=im.crop((0,max(0,size[1]-320),size[0],size[1])); bottom.load()
        bottom_sha=hashlib.sha256(bottom.tobytes()).hexdigest()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'dimensions':list(size),
            'chunks':chunks,'iend':True,'crc':'pass','decode':'pass','bottomPixelsSha256':bottom_sha}

def atomic_png(path,data):
    result=inspect_png(data);path=Path(path)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb')as f:f.write(data);f.flush();os.fsync(f.fileno())
        assert inspect_png(Path(tmp).read_bytes())==result
        os.replace(tmp,path)
        dfd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(dfd)
        finally:os.close(dfd)
        assert inspect_png(path.read_bytes())==result
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return result
