def parse_bank_islam(path):
    print("DEBUG parse_bank_islam received:", type(path), path if isinstance(path, str) else "(non-string)")
    
    if isinstance(path, (bytes, bytearray)):
        doc = fitz.open(stream=path, filetype="pdf")
    elif isinstance(path, str):
        doc = fitz.open(path)
    else:
        raise TypeError(f"parse_bank_islam expected bytes or filepath string, but got {type(path)}")
