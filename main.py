#Samar salah
#Enas 
#Shurooq 

import argparse
import base64
import configparser
import json
import threading
import time

import pyaudio
import websocket
from websocket._abnf import ABNF

from pprint import pprint


 #setup our text-to-speech module
from ibm_watson import TextToSpeechV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator #Authenticate our Model

from ibm_watson import SpeechToTextV1
from ibm_watson.websocket import RecognizeCallback, AudioSource 

 # Creds Text to Speech
apikey = 'apikey'
url = 'url' 
# Creds Speech to Text
speech_apikey = "apikey"
speech_url = "url"



CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 5
FINALS = []
LAST = None
text = []    #store from mic
REGION_MAP = {
    'us-east': 'gateway-wdc.watsonplatform.net',
    'us-south': 'stream.watsonplatform.net',
    'eu-gb': 'stream.watsonplatform.net',
    'eu-de': 'stream-fra.watsonplatform.net',
    'au-syd': 'gateway-syd.watsonplatform.net',
    'jp-tok': 'gateway-syd.watsonplatform.net',
}

def read_audio(ws, timeout):
    """Read audio and sent it to the websocket port.
    This uses pyaudio to read from a device in chunks and send these
    over the websocket wire.
    """
    global RATE
    p = pyaudio.PyAudio()
    # NOTE(sdague): if you don't seem to be getting anything off of
    # this you might need to specify:
    #
    #    input_device_index=N,
    #
    # Where N is an int. You'll need to do a dump of your input
    # devices to figure out which one you want.
    RATE = int(p.get_default_input_device_info()['defaultSampleRate'])
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("* recording")
    rec = timeout or RECORD_SECONDS

    for i in range(0, int(RATE / CHUNK * rec)):
        data = stream.read(CHUNK)
        ws.send(data, ABNF.OPCODE_BINARY)

    # Disconnect the audio stream
    stream.stop_stream()
    stream.close()
    print("* done recording")

    # In order to get a final response from STT we send a stop, this
    # will force a final=True return message.
    data = {"action": "stop"}
    ws.send(json.dumps(data).encode('utf8'))
    # ... which we need to wait for before we shutdown the websocket
    time.sleep(1)

#inserting the text recorded in a file
    if LAST:
        FINALS.append(LAST)
    transcript = "".join([x['results'][0]['alternatives'][0]['transcript']
                          for x in FINALS])
    print(transcript)
    file_object = open('recorded.txt', 'a')
    file_object.write(transcript)
    file_object.close()
    ws.close()

    # ... and kill the audio device
    p.terminate()


def on_message(self, msg):
    """Print whatever messages come in.
    While we are processing any non trivial stream of speech Watson
    will start chunking results into bits of transcripts that it
    considers "final", and start on a new stretch. It's not always
    clear why it does this. However, it means that as we are
    processing text, any time we see a final chunk, we need to save it
    off for later.
    """
    
    
    
    global LAST
    data = json.loads(msg)
    if "results" in data:
        if data["results"][0]["final"]:
            FINALS.append(data)
            LAST = None
        else:
            LAST = data
        # This prints out the current fragment that we are working on
        print(data['results'][0]['alternatives'][0]['transcript'])
        
 
def on_error(self, error):
    """Print any errors."""
    print(error)


def on_close(ws):
    print("in close")
    """Upon close, print the complete and final transcript."""
    global LAST
    if LAST:
        FINALS.append(LAST)
    transcript = "".join([x['results'][0]['alternatives'][0]['transcript']
                          for x in FINALS])
    print(transcript)
   


def on_open(ws):
    print(ws)
    print(ws.args)
    """Triggered as soon a we have an active connection."""
    args = ws.args
    data = {
        "action": "start",
        # this means we get to send it straight raw sampling
        "content-type": "audio/l16;rate=%d" % RATE,
        "continuous": True,
        "interim_results": True,
        # "inactivity_timeout": 5, # in order to use this effectively
        # you need other tests to handle what happens if the socket is
        # closed by the server.
        "word_confidence": True,
        "timestamps": True,
        "max_alternatives": 3
    }

    # Send the initial control message which sets expectations for the
    # binary stream that follows:
    ws.send(json.dumps(data).encode('utf8'))
    # Spin off a dedicated thread where we are going to read and
    # stream out audio.
    threading.Thread(target=read_audio,
                     args=(ws, args.timeout)).start()

def get_url():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    # See
    # https://console.bluemix.net/docs/services/speech-to-text/websockets.html#websockets
    # for details on which endpoints are for each region.
    region = config.get('auth', 'region')
    host = REGION_MAP[region]
  
    return ("wss://api.eu-gb.speech-to-text.watson.cloud.ibm.com/instances/0cf78329-bc4c-47a3-9c80-29916885848d/v1/recognize")
          
def get_auth():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    apikey = config.get('auth', 'apikey')
    return ("apikey", apikey)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Transcribe Watson text in real time')
    parser.add_argument('-t', '--timeout', type=int, default=20)
    args = parser.parse_args()
    return args






def runTextToSpeech():
    
  #setup service
    authenticator = IAMAuthenticator(apikey)
 #Create our service
    tts = TextToSpeechV1(authenticator=authenticator)
 #set the IBM service url
    tts.set_service_url(url)
    print("connecting")
    return tts
def runSpeechToText():
    authenticator = IAMAuthenticator(speech_apikey)
    stt = SpeechToTextV1(authenticator=authenticator)
    stt.set_service_url(speech_url)
    return stt    

while 1:
    print("1: Text to Speech from line input")
    print("2: Text to Speech from a text file")
    print("3: Speech To Text from an audio file")
    print("4: Speech to Text from mic")
    inp = int(input("Enter a number: "))

    if inp == 1:
        tts = runTextToSpeech()
        inp = input("Type your text...")
        with open('./speech.mp3', 'wb') as audio_file:
         res = tts.synthesize(inp, accept='audio/mp3', voice='en-US_AllisonV3Voice').get_result()
         audio_file.write(res.content) #write the content to the audio file
    elif inp == 2:
        tts = runTextToSpeech()
        inp = input("Type file name...")
        #testing our model using an audio file
        try:
            with open(inp, 'r') as f:
                text = f.readlines()
                text = [line.replace('\n','') for line in text] #replacing the line indicator with spaces
                text = ''.join(str(line) for line in text) #concatenate and feed it to the module.
                with open('./winston.mp3', 'wb') as audio_file:
                    res = tts.synthesize(text, accept='audio/mp3', voice='en-GB_JamesV3Voice').get_result() #selecting the audio format and voice
                    audio_file.write(res.content) #writing the contents from text file to a audio file
        except:
            print("File not found!!")

                
    elif inp == 3:
        stt = runSpeechToText()
        inp = input("Type file name...")
      
        #testing our model using an audio file
        try:
            with open(inp, 'rb') as f:
                res = stt.recognize(audio=f, content_type='audio/mp3', model='en-US_NarrowbandModel', continuous=True).get_result()
            text = res['results'][0]['alternatives'][0]['transcript']
            print(text)
            with open('TextFromAudioFile.txt', 'w') as out:
                out.writelines(text)
        except:
          print("File not found!!")
        
    elif inp == 4:
        headers = {}
        userpass = ":".join(get_auth())
        headers["Authorization"] = "Basic " + base64.b64encode(
            userpass.encode()).decode()
        url = get_url()

        ws = websocket.WebSocketApp(url,
                                    header=headers,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close)
    
        
        ws.on_open = on_open
        
        ws.args = parse_args()
        # This gives control over the WebSocketApp. This is a blocking
        # call, so it won't return until the ws.close() gets called (after
        # 6 seconds in the dedicated thread).
        ws.run_forever()

          
    




