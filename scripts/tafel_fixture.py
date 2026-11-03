"""Local HTTP/TLS test browser; private cookies never appear in evidence."""
import http.client,json,socket,ssl
from http.cookies import SimpleCookie
class Client:
    def __init__(self,port=44961,host="localhost",ca=None):
        self.cookies={};self.cookie_options={};self.port=port;self.host=host;self.ca=ca
    def call(self,method,path,body=None,headers=None,expected=200):
        headers=dict(headers or {})
        if self.cookies:headers["Cookie"]="; ".join(k+"="+v for k,v in self.cookies.items())
        if body is not None and not isinstance(body,bytes):
            body=json.dumps(body).encode();headers["Content-Type"]="application/json"
        if self.ca:
            context=ssl.create_default_context(cafile=str(self.ca))
            conn=http.client.HTTPSConnection(self.host,self.port,context=context,timeout=20)
            conn.sock=context.wrap_socket(socket.create_connection(("127.0.0.1",self.port),timeout=20),server_hostname=self.host)
        else:conn=http.client.HTTPConnection("127.0.0.1",self.port,timeout=20)
        conn.request(method,path,body,headers);response=conn.getresponse();data=response.read()
        for name,value in response.getheaders():
            if name.lower()=="set-cookie":
                cookie=SimpleCookie();cookie.load(value)
                for key,value in cookie.items():
                    self.cookie_options[key]={"secure":bool(value["secure"]),"httponly":bool(value["httponly"]),"samesite":value["samesite"]}
                    if value.value:self.cookies[key]=value.value
                    else:self.cookies.pop(key,None)
        assert response.status==expected,f"{method} {path.split('?')[0]} returned {response.status}, expected {expected}"
        conn.close()
        try:return json.loads(data)
        except ValueError:return data
