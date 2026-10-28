"""Trust local listener names, never an arbitrary request Host or proxy header."""
from urllib.parse import urlsplit

def trusted_request(headers, port):
    hosts = headers.get_all('Host', [])
    origins = headers.get_all('Origin', [])
    if len(hosts) != 1 or len(origins) > 1:
        return False
    authorities = {f'127.0.0.1:{port}', f'localhost:{port}', f'[::1]:{port}'}
    if port == 80:
        authorities.update({'127.0.0.1', 'localhost', '[::1]'})
    if hosts[0].lower() not in authorities:
        return False
    if origins and origins[0].lower() not in {'http://' + x for x in authorities}:
        return False
    # Browser fetch metadata also blocks cross-site requests with absent Origin.
    return headers.get('Sec-Fetch-Site', '') not in {'cross-site'}
