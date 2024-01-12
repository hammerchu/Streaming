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
import cv2

class DailyYOLO(EventHandler):
    def __init__(self):
        '''A call client is used to join a meeting, handle meeting events, sending/receiving audio and video, etc.'''
        self.__client = CallClient(event_handler = self)

        # self.__model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)

        self.__cap = cv2.VideoCapture(0)

        # Check if the camera is opened correctly
        if not self.__cap.isOpened():
            print("ERROR - Failed to open camera")
        
        self.__camera = None

        self.__time = time.time()

        self.__participate = self.__client.participants()
        InputSettings = {
            "camera" : {
                "isEnabled" : True,
                # "settings" : 
            }
        }
        # print(f'\n user input Pre: {self.__client.inputs()}')
        # self.__client.update_inputs(InputSettings)
        # print(f'\n self.__participate: {json.dumps(self.__participate["local"]["id"], indent=4)}\n')
        # print(f'\n user input Post: {self.__client.inputs()}')
        # print(f'\n subscription_profiles: {self.__client.subscription_profiles()}')



        self.__queue = queue.Queue()

        self.__app_quit = False

        self.video_width = None

        '''kick off frame processing in thread'''
        self.__thread_cam = threading.Thread(target = self.get_cam_frame)
        self.__thread_frame = threading.Thread(target = self.process_frames)
        self.__thread_cam.start()
        self.__thread_frame.start()

    def run(self, meeting_url):
        print(f"Connecting to {meeting_url}...")
        self.__client.join(meeting_url)
        self.__client.set_user_name("Bot147")

        print("Waiting for participants to join...")
        self.__thread_cam.join()
        self.__thread_frame.join()

    def leave(self):
        self.__app_quit = True
        self.__thread_cam.join()
        self.__thread_frame.join()
        self.__client.leave()

    def on_participant_joined(self, participant):
        print(f"Participant {participant['id']} joined, analyzing frames...")
        # self.__client.set_video_renderer(participant["id"], self.on_video_frame, video_source='camera')
        # self.__client.set_video_renderer(self.__participate["local"]["id"], self.on_video_frame, video_source='camera')

    def setup_camera(self, video_frame):
        ''' Define a daily virtual camera '''
        if not self.__camera:
            self.__camera = Daily.create_camera_device("camera",
                                                       width = int(video_frame.shape[1]),
                                                       height = int(video_frame.shape[0]),
                                                       color_format="RGB")
            # self.__camera = Daily.create_camera_device("camera",
            #                                            width = int(video_frame.width),
            #                                            height = int(video_frame.height),
            #                                            color_format="RGB")
            self.__client.update_inputs({
                "camera": {
                    "isEnabled": True,
                    "settings": {
                        "deviceId": "camera"
                    }
                }
            })

    def process_frames_original(self): # original from daily-example
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

    def process_frames(self): # original from daily-example
        '''Prepare frame for the daily virtual -camera object '''
        index = 0 
        while not self.__app_quit:
            frame = self.__queue.get()
            frame_bytes = cv2.imencode('.jpg', frame)[1].tobytes()
    
            self.__camera.write_frame(frame_bytes)
            index += 1

    def on_video_frame(self, participant_id, video_frame):
        '''A callback to be called on every received frame'''
        # print('\nRunning on_video_frame \n')
        # Process ~15 frames per second (considering incoming frames at 30fps).
        if time.time() - self.__time > 0.05:
            self.__time = time.time()
            self.setup_camera(video_frame)
            self.__queue.put(video_frame)

    def get_cam_frame(self):

        ret, frame = self.__cap.read()
        isPrinted = False

        # Check if the frame was successfully read
        if not ret:
            print("ERROR - Failed to capture frame")
        if not isPrinted:
            print('Frame: ', frame.shape)
            isPrinted = True

        cv2.putText(frame, "OBB", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
        
        self.setup_camera(frame)
        self.__queue.put(frame)


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