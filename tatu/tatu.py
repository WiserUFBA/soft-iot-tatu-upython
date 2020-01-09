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


topicPrefix = "dev/"

class minhaThread:
    
  def __init__(self, deviceName, sensorName, met, topic, topicError, pub_client, collectTime, publishTime):
    self.threadID = (met + "_" + deviceName + "_" + sensorName)
    self.deviceName = deviceName
    self.sensorName = sensorName
    self.met = met
    self.topic = topic
    self.topicError = topicError
    self.pub_client = pub_client
    self.publishTime = publishTime/1000
    self.collectTime = collectTime/1000

  def start(self):
    _thread.start_new_thread(self.run, ())

  def run(self):
    print ("Starting thread " + self.threadID)

    if (self.met == "FLOW"):
      flow(self.deviceName, self.sensorName, self.topic, self.topicError, self.pub_client, self.collectTime, self.publishTime)
    elif (self.met == "EVENT"):
      event(self.deviceName, self.sensorName, self.topic, self.topicError, self.pub_client, self.collectTime, self.publishTime)
    elif (self.met == "GET"):
      get(self.deviceName, self.sensorName, self.topic, self.topicError, self.pub_client)
        
    #print ("Stopping thread " + self.threadID)


def main(data, msg):
  mqttBroker = data['mqttBroker']
  #mqttPort = data['mqttPort']
  #mqttUsername = data['mqttUsername']
  #mqttPassword = data['mqttPassword']
  deviceName = data['deviceName']
  #print (deviceName)
  topic = str.encode(topicPrefix + deviceName + "/RES")
  topicError = str.encode(topicPrefix + deviceName + "/ERR")
    
  msg = msg.decode("utf-8")
  msgList = msg.split(" ")
  met = msgList[0]
  sensorName = msgList[2]

  idP = met + '_' + deviceName + '_' + sensorName
  pub_client = MQTTClient(idP, mqttBroker)

  if (met=="GET"):
    collectTime = 0
    publishTime = 0

  elif (met=="FLOW"):
    try:
      msgConf = (str(msgList[3]) + str(msgList[4]))
    except:
      msgConf = (str(msgList[3]))

    config = ujson.loads(msgConf)
    collectTime = config["collect"]
    publishTime = config["publish"]
    
  elif (met=="EVENT"):
    msgConf = (str(msgList[3]))
    config = ujson.loads(msgConf)
    collectTime = config["collect"]
    publishTime = 0
  
  t1 = minhaThread(deviceName, sensorName, met, topic, topicError, pub_client, collectTime, publishTime)
  t1.start()

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
        #Request: FLOW VALUE sensorName {"collect":collectTime,"publish":publishTime}
        responseModel = {"CODE":"POST","METHOD":"FLOW","HEADER":{"NAME":deviceName},"BODY":{sensorName:listValues,"FLOW":{"collect":(collectTime*1000),"publish":(publishTime*1000)}}}
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

  
  
  

def event(deviceName, sensorName, topic, topicError, pub_client, collectTime, publishTime):
  pub_client.connect()
  try:
    methodEvent = getattr(sensors, sensorName)
    value = methodEvent()

    #Request: EVENT VALUE sensorName {"collect":collectTime}
    responseModel = {"CODE":"POST","METHOD":"EVENT","HEADER":{"NAME":deviceName},"BODY":{sensorName:value,"EVENT":{"collect":(collectTime*1000),"publish":(publishTime*1000)}}}

    response = ujson.dumps(responseModel)
    pub_client.publish(topic, response)

    while True:
      time.sleep(collectTime)
      publishTime = publishTime + collectTime
      aux = methodEvent()
      if aux!=value:
        value = aux
        #Request: EVENT VALUE sensorName {"collect":collectTime}
        responseModel = {"CODE":"POST","METHOD":"EVENT","HEADER":{"NAME":deviceName},"BODY":{sensorName:value,"EVENT":{"collect":(collectTime),"publish":(publishTime)}}}
        response = ujson.dumps(responseModel)
        pub_client.publish(topic, response)
  except Exception as e:
    print("Error: {0}".format(e))
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

    #Request:  #GET VALUE sensorName
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



























