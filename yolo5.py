import argparse
import queue
import time
# import torch
import threading
import io
from PIL import Image
import numpy as np
from daily import *
import json 

class DailyYOLO(EventHandler):
    def __init__(self):
        '''A call client is used to join a meeting, handle meeting events, sending/receiving audio and video, etc.'''
        self.__client = CallClient(event_handler = self)

        # self.__model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
        
        self.__camera = None

        self.__time = time.time()

        self.__participate = self.__client.participants()
        InputSettings = {
            "camera" : {
                "isEnabled" : True,
                # "settings" : 
            }
        }
        print(f'\n user input Pre: {self.__client.inputs()}')
        self.__client.update_inputs(InputSettings)
        print(f'\n self.__participate: {json.dumps(self.__participate["local"]["id"], indent=4)}\n')
        print(f'\n user input Post: {self.__client.inputs()}')
        print(f'\n subscription_profiles: {self.__client.subscription_profiles()}')



        self.__queue = queue.Queue()

        self.__app_quit = False

        self.video_width = None

        '''kick off frame processing in thread'''
        self.__thread = threading.Thread(target = self.process_frames)
        self.__thread.start()

    def run(self, meeting_url):
        print(f"Connecting to {meeting_url}...")
        self.__client.join(meeting_url)
        self.__client.set_user_name("Bot147")

        print("Waiting for participants to join...")
        self.__thread.join()

    def leave(self):
        self.__app_quit = True
        self.__thread.join()
        self.__client.leave()

    def on_participant_joined(self, participant):
        print(f"Participant {participant['id']} joined, analyzing frames...")
        # self.__client.set_video_renderer(participant["id"], self.on_video_frame, video_source='camera')
        self.__client.set_video_renderer(self.__participate["local"]["id"], self.on_video_frame, video_source='camera')

    def setup_camera(self, video_frame):
        ''' Define a daily virtual camera '''
        if not self.__camera:
            # self.__camera = Daily.create_camera_device("camera",
            #                                            width = 960,
            #                                            height = 540,
            #                                            color_format="RGB")
            self.__camera = Daily.create_camera_device("camera",
                                                       width = int(video_frame.width),
                                                       height = int(video_frame.height),
                                                       color_format="RGB")
            self.__client.update_inputs({
                "camera": {
                    "isEnabled": True,
                    "settings": {
                        "deviceId": "camera"
                    }
                }
            })

    def process_frames(self):
        '''Prepare frame for the daily virtual -camera object '''
        index = 0 
        while not self.__app_quit:
            video_frame = self.__queue.get()
            image = Image.frombytes("RGBA", (video_frame.width, video_frame.height), video_frame.buffer)#.resize((960, 540))

            ''' Update the virtual camera if video frame has changed'''
            # if self.video_width != video_frame.width:
            #     print('Update camera setup')
            #     self.setup_camera(video_frame)
            #     self.video_width = video_frame.width

            img_array = np.array(image)[:, :, :3] # remove Alpha channel

            ''' stitch multiple cam together into one single frame'''
 
            pil = Image.fromarray(img_array, mode="RGB").tobytes()

            # if index%30 == 0:
            #     ''' print out some info every 30 frames '''
            #     print(f' img_array : { img_array.shape} ')
            #     print(f' video_frame : {video_frame.height}, { video_frame.width}  ')
                # print(f' image : { type(image)} ')
                # print(f' result : { type(result)} ')
                # print(f' result.render()[0] : { type(result.render()[0])} - { result.render()[0].shape} ')
                # image.save('test_01.png')
    
            self.__camera.write_frame(pil)
            index += 1

    def on_video_frame(self, participant_id, video_frame):
        '''A callback to be called on every received frame'''
        # print('\nRunning on_video_frame \n')
        # Process ~15 frames per second (considering incoming frames at 30fps).
        if time.time() - self.__time > 0.05:
            self.__time = time.time()
            self.setup_camera(video_frame)
            self.__queue.put(video_frame)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--meeting", required = True, help = "Meeting URL")
    args = parser.parse_args()

    Daily.init()

    app = DailyYOLO()

    try :
        app.run(args.meeting)
    except KeyboardInterrupt:
        print("Ctrl-C detected. Exiting!")
    finally:
        app.leave()

    # Let leave finish
    time.sleep(2)

if __name__ == '__main__':
    main()