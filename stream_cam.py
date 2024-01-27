#

#
# Usage: python stream_cam.py -si m -fr 60 -sv 0
#
import os
import argparse
import time
import threading

from daily import *
from PIL import Image
import cv2
import json

from datetime import datetime
import numpy as np
import queue

class SendImageApp(EventHandler): # require EventHandler for callbacks
    '''
    Based on send_image.py from daily-pfourcc = cv2.VideoWriter_fourcc(*'avc1')
        self._video = cv2.VideoWriter("test.mp4",fourcc, 60,videodims)ython example 
    '''
    def __init__(self, size, framerate, is_save_to_disk):

        # self.fps = 0  # Variable to store frames per second
        # self.resolution = (0, 0)  # Variable to store frame resolution
        self.last_fps_update = time.time()  # Variable to store the last time FPS was updated

        self.read_frame_fps = 0

        # self.__image = Image.open(image_file)
        self.frame_queue = queue.Queue()  

        self.__framerate = framerate
        self._pil_image = None

        self.record_video_path = '/home/hammer/DEV/OBB/streaming/records'

        self.video_quality = "low"

        self.video_record_dims = (640*3, 480) # fix video width for recording

        if size.lower() == 'l':
            self.w = 1920
            self.h = 1080

        elif size.lower() == 'm':
            self.w = 1280
            self.h = 720

        elif size.lower() == 's':
            self.w = 640
            self.h = 480
        else:
            self.w = 640
            self.h = 480

        
        # self.__cap = cv2.VideoCapture(1) # v4l2-ctl --list-devices
        # self.__cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        # self.__cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
        # self.__cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
        # self.__cap.set(cv2.CAP_PROP_FPS, self.__framerate)
        # ret, frame = self.__cap.read()
        # if not ret:
        #     print("ERROR - Failed to capture frame")

        self.create_camera()
        # self.__camera = Daily.create_camera_device("my-camera",
        #                                            width = frame.shape[1]*3,
        #                                            height = frame.shape[0],
        #                                            color_format = "RGB")

        self.__client = CallClient(event_handler = self) # add eventhandler here too

        self.__client.update_inputs({
            "camera": {
                "isEnabled": True,
                "settings": {
                    "deviceId": "my-camera"
                }
            },
            "microphone": False
        }, completion = self.on_inputs_updated_)

        self.__client.update_subscription_profiles({
            "base": {
                "camera": "unsubscribed",
                "microphone": "unsubscribed"
            }
        })

        self.__app_quit = False
        self.__app_error = None
        self.__app_joined = False
        self.__app_inputs_updated = False
        self.__report_data = True

        self.__start_event = threading.Event()
        self.__thread_read_frame = threading.Thread(target = self.read_frames)
        self.__thread_read_frame.start()
        self.__thread_send_image = threading.Thread(target = self.send_image)
        self.__thread_send_image.start()
        self.__thread_send_data = threading.Thread(target = self.send_data_regularly)
        self.__thread_send_data.start()

        '''If we want to save the video to disk'''
        if is_save_to_disk:
            
            print(f'Recording at {self.video_record_dims}')

            # create the folder for today if its not exist yet
            folder_today = os.path.join(self.record_video_path, datetime.now().strftime('%Y%m%d'))
            if not os.path.exists(folder_today):
                os.makedirs(folder_today)
                
            fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
            self._video = cv2.VideoWriter(f"{os.path.join(folder_today, datetime.now().strftime('%Y%m%d_%H%M%S'))}.mp4",fourcc, self.__framerate,self.videodims)

            self.__thread_record_video = threading.Thread(target = self.record_video)
            self.__thread_record_video.start()

    def create_camera(self):
        self.__camera = Daily.create_camera_device("my-camera",
                                                   width = self.w*3,
                                                   height = self.h,
                                                   color_format = "RGB")
    
    def read_frames(self):

        self.__cap = cv2.VideoCapture(1) # v4l2-ctl --list-devices
        self.__cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        self.__cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
        self.__cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)
        # self.__cap.set(cv2.CAP_PROP_FPS, self.__framerate)
        self.__cap.set(cv2.CAP_PROP_FPS, 30)



        fps_start_time = time.time()
        fps_counter = 0
        fps = 0

        while True:
            ret, frame = self.__cap.read()  # Read a frame from the video capture device

            # frame = cv2.resize(frame, (640, 480))

            if not ret:
                print("Error: Unable to read frame from camera")
                break

            self.frame_queue.put(frame)  # Put the frame into the frame queue
            
            fps_counter += 1
            if time.time() - fps_start_time >= 1:
                self.read_frame_fps = fps_counter / (time.time() - fps_start_time)
                fps_counter = 0
                fps_start_time = time.time()

        self.__cap.release()

    def on_inputs_updated_(self, inputs, error):
        if error:
            print(f"Unable to updated inputs: {error}")
            self.__app_error = error
        else:
            self.__app_inputs_updated = True
        self.maybe_start()

    def on_joined(self, data, error):
        if error:
            print(f"Unable to join meeting: {error}")
            self.__app_error = error
        else:
            self.__app_joined = True
        self.maybe_start()

    def run(self, meeting_url):
        self.__client.join(meeting_url, completion=self.on_joined)
        self.__thread_read_frame.join()
        self.__thread_send_image.join()
        self.__thread_send_data.join()
        try:
            self.__thread_record_video.join()
        except:
            print('video not recording to disk')

    def leave(self):
        self.__app_quit = True
        self.__thread_read_frame.join()
        self.__thread_send_image.join()
        self.__thread_send_data.join()
        try:
            self.__thread_record_video.join()
        except:
            print('video not recording to disk')

        self.__client.leave()

    def maybe_start(self):
        if self.__app_error:
            self.__start_event.set()

        if self.__app_inputs_updated and self.__app_joined:
            self.__start_event.set()

    def send_image(self):
        self.__start_event.wait()
        print('send_image')
        if self.__app_error:
            print(f"Unable to s-send audio!")
            return

        sleep_time = 1.0 / self.__framerate

        # Initialize variables for FPS calculation
        fps_start_time = time.time()
        fps_counter = 0
        fps = 0

        while not self.__app_quit:
            '''Read frame'''
            # ret, frame = self.__cap.read()
            frame = self.frame_queue.get()  # Get a frame from the frame queue

            # if not ret:
            #     print("ERROR - Failed to capture frame")

            # Calculate FPS
            fps_counter += 1
            if time.time() - fps_start_time >= 1:
                fps = fps_counter / (time.time() - fps_start_time)
                fps_counter = 0
                fps_start_time = time.time()
            
            cv2.putText(frame, f"{self.w}x{self.h}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 200), 2, cv2.LINE_AA)
            cv2.putText(frame, f"DY FPS: {fps:.2f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 200), 2, cv2.LINE_AA)
            cv2.putText(frame, f"RF FPS: {self.read_frame_fps:.2f}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 200), 2, cv2.LINE_AA)

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Merge frames horizontally
            merged_frame = cv2.hconcat([frame, frame, frame])

            # self._pil_image=Image.fromarray(merged_frame)
            print(f'w {self.w} : h {self.h}')
            self._pil_image=Image.fromarray(merged_frame).resize((self.w*3, self.h))

            ''' Save test frame onto disk'''
            # self._pil_image.save(f"{datetime.now().strftime('%Y%m%d_%H%M')}.jpg")

            self.__camera.write_frame(self._pil_image.tobytes())

            time.sleep(sleep_time)
    
    def record_video(self):
        while not self.__app_quit:
            if self._pil_image != None:
                # record the frame to local drive 
                pil_img = self._pil_image.resize(self.videodims)
                print('valid frame')
            else:
                # record a black frame
                pil_img = Image.new('RGB', self.videodims, color = 'darkred')
                print('empty frame')

            self._video.write(cv2.cvtColor(np.array(pil_img.copy()), cv2.COLOR_RGB2BGR))

            # sleep_time = 1.0 / self.__framerate
            # time.sleep(sleep_time)

        self._video.release()

    def on_app_message(self, message, sender_id):
        try:
            print('Received message: ', message['message'], ' from ', message['name'])

            '''
            TBA
            '''
            if 'size@l' in message['message']:
                self.update_video_res('l')
            elif 'size@m' in message['message']:
                self.update_video_res('m')
            elif 'size@s' in message['message']:
                self.update_video_res('s')

        except Exception as e:
            print(e)
    
    def update_video_res(self, new_res:str):
        '''
        Dynamically update the video res
        '''
        print('updating video res: ', new_res)

        if new_res == 'l':
            self.video_quality = "high"
        elif new_res == 'm':
            self.video_quality = "medium"
        elif new_res == 's':
            self.video_quality = "low"

        
        self.__client.update_publishing(
            {
                "camera": {
                    "isPublishing": True,
                    "sendSettings": {
                        "maxQuality" : self.video_quality
                    }
                },
                "microphone": False


            },completion=None)

        # self.__client.update_inputs({
        #     "camera": {
        #         "isEnabled": True,
        #         "settings": {
        #             "width": self.w,
        #             "height": self.h
        #         }
        #     },
        #     "microphone": False
        # }, completion = self.on_inputs_updated_)
    
    def send_message(self, message):
        self.__client.send_app_message(message)
        print('Sent message: ', message)

    def send_data_regularly(self):
        while not self.__app_quit:
            if self.__report_data:
                data = {"message": "obb-sys@example bot performance data", "timestamp": datetime.now().strftime('%m/%d/%Y, %H:%M:%S')}
                self.send_message(json.dumps(data))
            time.sleep(5000)
        

def main():
    parser = argparse.ArgumentParser()
    # parser.add_argument("-m", "--meeting", required = True, help = "Meeting URL")
    parser.add_argument("-si", "--size", required = True, help = "Size of video, L, M or S")
    parser.add_argument("-fr", "--framerate", type=int, required = True, help = "Framerate, recommend 30")
    parser.add_argument("-sv", "--save", type=int, required = True, help = "save video to disk")
    args = parser.parse_args()

    Daily.init()

    # app = SendImageApp(args.image, args.framerate)
    app = SendImageApp(args.size, args.framerate, args.save)

    try :
        # app.run(args.meeting)
        app.run('https://onbotbot.daily.co/_test')
    except KeyboardInterrupt:
        print("Ctrl-C detected. Exiting!")
    finally:
        app.leave()
        

    # Let leave finish
    time.sleep(2)

if __name__ == '__main__':
    main()
