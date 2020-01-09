import machine
import micropython
import time
import esp
esp.osdebug(None)
import gc
gc.collect()


import sensors
import ujson
import _thread

import upip
upip.install("umqtt.robust")
from umqtt.robust import MQTTClient


def start(data, msg):
  #print("teste 1")
  mqttBroker = data['mqttBroker']
  #mqttPort = data['mqttPort']
  #mqttUsername = data['mqttUsername']
  #mqttPassword = data['mqttPassword']
  deviceName = data['deviceName']
  topic = str.encode(data['topicPrefix'] + deviceName + data['topicRes'])
  topicError = str.encode(data['topicPrefix'] + deviceName + data['topicErr'])
  #print(mqttBroker)
  #print(topic, msg)
  
  msgJson = ujson.loads(msg)
  sensorName = msgJson["sensor"]
  met = msgJson["method"]
  
  #print (sensorName, met)
  idP = met + '_' + deviceName + '_' + sensorName
  #print (idP)
  pub_client = MQTTClient(idP, mqttBroker)
  if (met=="STOP"):
    print ("stop")
    
  elif (met=="POST"):
    print ("post")
    
  else:
    if (met=="GET"):
      get(deviceName, sensorName, topic, topicError, pub_client)
      
    elif (met=="FLOW"):
      time = msgJson["time"]
      collectTime = time["collect"]
      publishTime = time["publish"]
      flow(deviceName, sensorName, topic, topicError, pub_client, collectTime, publishTime)
      
    elif (met=="EVENT"):
      print ("event")
      
     
def flow(deviceName, sensorName, topic, topicError, pub_client, collectTime, publishTime):
  pub_client.connect()
  t = 0
  try:
    method = getattr(sensors, sensorName)
    listValues = []
    while True:
      listValues.append(str(method()))
      t = t + collectTime
      if (t >= publishTime):
        #Request: {"method":"FLOW", "sensor":"sensorName", "time":{"collect":collectTime,"publish":publishTime}}
        responseModel = {"CODE":"POST","METHOD":"FLOW","HEADER":{"NAME":deviceName},"BODY":{sensorName:listValues,"FLOW":{"collect":(collectTime),"publish":(publishTime)}}}
        response = ujson.dumps(responseModel)
        pub_client.publish(topic, response)
        t = 0
        listValues = []
      time.sleep(collectTime)
  except:
    errorMessage = "There is no " + sensorName + " sensor in device " + deviceName
    errorNumber = 1
    responseModel = {"code":"ERROR", "number":errorNumber, "message":errorMessage}
    response = ujson.dumps(responseModel)
    pub_client.publish(topicError, response)

  pub_client.disconnect()


def get(deviceName, sensorName, topic, topicError, pub_client):
  pub_client.connect()
  try:
    method = getattr(sensors, sensorName)
    value = method()

    #Request: {"method":"GET", "sensor":"sensorName"}
    responseModel = {'CODE':'POST','METHOD':'GET','HEADER':{'NAME':deviceName},'BODY':{sensorName:value}}
    response = ujson.dumps(responseModel)
    pub_client.publish(topic, response)
  except:
    errorMessage = "There is no " + sensorName + " sensor in device " + deviceName
    errorNumber = 1
    responseModel = {"code":"ERROR", "number":errorNumber, "message":errorMessage}
    response = ujson.dumps(responseModel)
    pub_client.publish(topicError, response)
  
  pub_client.disconnect()










































































