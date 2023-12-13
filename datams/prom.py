import  os, json
os.environ["PROMETHEUS_DISABLE_CREATED_SERIES"]="true"

'''
Usage 
initiate at startup to enable components to test if prom is enabled
as 

from _prom import initPom
if "prometheus" in config:
    initPom(config["prometheus"])

One can also test if 'pom_registry' is valid, it will only assigned if init_pom has successfully run

the port can be assigned/overridden with env var PROMETHEUS_PORT
config 
 if 'pushhost' is present, we push to collector and port is used for that service, 
 also required are 'port' 'prometheus-context'
 port - the port to publish metrics (most commmon use case)
 
if 'sd-config-path' is present, we write our scrape info (generally not needed)



add gauges, increments and info

from _prom import createGauge,createInfo, createIncrements
_pgauge_registered =  createGauge("processes_registered","Registered Processes")

add a callback instead of updating the metric every time 
_pgauge_registered.callback(self._gauge_registered)

as i.e. 
def _gauge_registered(self):
    return int(len(self._processStore))

'''




from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily,REGISTRY as PROM_registry
from prometheus_client.exposition import make_wsgi_app,_SilentHandler,ThreadingWSGIServer

from prometheus_client import Gauge,Counter,Info,Histogram


pom_server = None
pom_server_gauge = None
pom_registry = None
pom_context = None
pom_push_url = None



def __start_prom_server(port):
    import threading
    from wsgiref.simple_server import make_server
    app = make_wsgi_app()
    httpd = make_server('', port, app, ThreadingWSGIServer, handler_class=_SilentHandler)
    t = threading.Thread(target=httpd.serve_forever)
    t.daemon = True
    t.start()
    return httpd
    
    
    

def initPomScrape(port):
    global pom_server
    global pom_server_gauge
    global pom_registry
    if  pom_server is None:
        pom_registry = PROM_registry
        pom_server = __start_prom_server(int(float(port)))
        pom_server_gauge = Gauge('up','service status')
        
        
def initPomPush(host,port,context):
    global pom_server
    global pom_server_gauge
    global pom_registry
    global pom_context
    global pom_push_url
    
    if  pom_server is None:
        pom_context = context
        from prometheus_client import CollectorRegistry, Gauge, push_to_gateway,pushadd_to_gateway
        pom_registry = CollectorRegistry()
        pom_push_url = f'{host}:{port}'
        pom_server = push_to_gateway(pom_push_url, job=context, registry=pom_registry)
        pom_server_gauge = Gauge('up','service status', registry=pom_registry)
        
        
        
def initPom(config):
    
    if "pushhost" in config:
        initPomPush(config["pushhost"],config["port"], config["prometheus-context"] )
    else:
        initPomScrape(os.getenv("PROMETHEUS_PORT", str(config["port"])))
        if "sd-config-path" in config:
            #print(config)
            with open(os.path.expanduser(config["sd-config-path"].format(config["prometheus-context"])),'w') as fp:
                scrapeconfig = {}
                scrapeconfig["targets"]=["localhost:{}".format(os.getenv("PROMETHEUS_PORT", config["port"]))]
                scrapeconfig["labels"]={"context":config["prometheus-context"]}
                #print(scrapeconfig)
                json.dump([scrapeconfig],fp)
                
    
    
    
        
def start_pom():
    
    global pom_server_gauge
    if  not pom_server_gauge is None:
        #raise ValueError("MQ prometheus service has not been initialised!")
        pom_server_gauge.set(1)
        
            
    
    #pass 
        
def stop_pom():
    global pom_server
    if  not pom_server is None:
        #raise ValueError("MQ prometheus service has not been initialised!")
        from prometheus_client import push_to_gateway,pushadd_to_gateway,delete_from_gateway
        if isinstance(pom_server,(push_to_gateway,pushadd_to_gateway)):
            global pom_context
            global pom_push_url
            print("disconnecting {} from {} ".format(pom_context,pom_push_url))
            delete_from_gateway(pom_push_url,pom_context)
        else:
            print("stopping no push gateway")
        
        if hasattr(pom_server,"shutdown"):
            pom_server.shutdown()
        
        
def _ensureValid(name):
    return name.replace('-','_').replace(' ','').replace('.','')

class HumanBytes:
    from typing import List, Union
    
    METRIC_LABELS: List[str] = ["B", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    BINARY_LABELS: List[str] = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
    PRECISION_OFFSETS: List[float] = [0.5, 0.05, 0.005, 0.0005] # PREDEFINED FOR SPEED.
    PRECISION_FORMATS: List[str] = ["{}{:.0f} {}", "{}{:.1f} {}", "{}{:.2f} {}", "{}{:.3f} {}"] # PREDEFINED FOR SPEED.

    @staticmethod
    def format(num: Union[int, float], metric: bool=False, precision: int=1) -> str:
        """
        Human-readable formatting of bytes, using binary (powers of 1024)
        or metric (powers of 1000) representation.
        """

        assert isinstance(num, (int, float)), "num must be an int or float"
        assert isinstance(metric, bool), "metric must be a bool"
        assert isinstance(precision, int) and precision >= 0 and precision <= 3, "precision must be an int (range 0-3)"

        unit_labels = HumanBytes.METRIC_LABELS if metric else HumanBytes.BINARY_LABELS
        last_label = unit_labels[-1]
        unit_step = 1000 if metric else 1024
        unit_step_thresh = unit_step - HumanBytes.PRECISION_OFFSETS[precision]

        is_negative = num < 0
        if is_negative: # Faster than ternary assignment or always running abs().
            num = abs(num)

        for unit in unit_labels:
            if num < unit_step_thresh:
                # VERY IMPORTANT:
                # Only accepts the CURRENT unit if we're BELOW the threshold where
                # float rounding behavior would place us into the NEXT unit: F.ex.
                # when rounding a float to 1 decimal, any number ">= 1023.95" will
                # be rounded to "1024.0". Obviously we don't want ugly output such
                # as "1024.0 KiB", since the proper term for that is "1.0 MiB".
                break
            if unit != last_label:
                # We only shrink the number if we HAVEN'T reached the last unit.
                # NOTE: These looped divisions accumulate floating point rounding
                # errors, but each new division pushes the rounding errors further
                # and further down in the decimals, so it doesn't matter at all.
                num /= unit_step

        return HumanBytes.PRECISION_FORMATS[precision].format("-" if is_negative else "", num, unit)
    
    

        
    
        
class MQIncrements(Counter):
    
    def update(self,val):
        self.inc(val)
        
    def deregister(self):
        pom_registry.unregister(self)
        
class MQGauge(Gauge):
    
    def update(self,val):
        self.set(val)
        
    def deregister(self):
        pom_registry.unregister(self)
        
        
    def callback(self, callbfunc):
        self.set_function(lambda:callbfunc())
        
        
def createGauge(name,desc):
    
    return MQGauge(_ensureValid(name), 'Gauge {}'.format(desc), registry=pom_registry) 
        

def createIncrements(name,desc):
    
    return MQIncrements(_ensureValid(name), 'Counter {}'.format(desc), registry=pom_registry) 


def createInfo(name,desc):
    return Info(_ensureValid(name), 'Info {}'.format(desc), registry=pom_registry)



    