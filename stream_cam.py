#
# This demo will join a Daily meeting and send a given image at the specified
# framerate using a virtual camera device.
#
# Usage: python3 send_image.py -m MEETING_URL -i IMAGE -f FRAME_RATE
#

import argparse
import time
import threading

from daily import *
from PIL import Image
import cv2



class SendImageApp:
    '''
    Based on send_image.py from daily-python example 
    '''
    def __init__(self, size, framerate):
        # self.__image = Image.open(image_file)
        self.__framerate = framerate

        if size.lower() == 'l':
            w = 1920
            h = 1080
        elif size.lower() == 'm':
            w = 1280
            h = 720
        elif size.lower() == 's':
            w = 640
            h = 480


        self.__cap = cv2.VideoCapture(0)
        self.__cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        self.__cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self.__cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        self.__cap.set(cv2.CAP_PROP_FPS, 60)
        ret, frame = self.__cap.read()
        if not ret:
            print("ERROR - Failed to capture frame")

        self.__camera = Daily.create_camera_device("my-camera",
                                                   width = frame.shape[1]*3,
                                                   height = frame.shape[0],
                                                   color_format = "RGB")

        self.__client = CallClient()

        self.__client.update_inputs({
            "camera": {
                "isEnabled": True,
                "settings": {
                    "deviceId": "my-camera"
                }
            },
            "microphone": False
        }, completion = self.on_inputs_updated)

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

        self.__start_event = threading.Event()
        self.__thread = threading.Thread(target = self.send_image);
        self.__thread.start()

    def on_inputs_updated(self, inputs, error):
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
        self.__thread.join()

    def leave(self):
        self.__app_quit = True
        self.__thread.join()
        self.__client.leave()

    def maybe_start(self):
        if self.__app_error:
            self.__start_event.set()

        if self.__app_inputs_updated and self.__app_joined:
            self.__start_event.set()

    def send_image(self):
        self.__start_event.wait()

        if self.__app_error:
            print(f"Unable to send audio!")
            return

        sleep_time = 1.0 / self.__framerate

        # Initialize variables for FPS calculation
        fps_start_time = time.time()
        fps_counter = 0
        fps = 0

        while not self.__app_quit:
            '''Read frame'''
            ret, frame = self.__cap.read()
            if not ret:
                print("ERROR - Failed to capture frame")

            # Calculate FPS
            fps_counter += 1
            if time.time() - fps_start_time >= 1:
                fps = fps_counter / (time.time() - fps_start_time)
                fps_counter = 0
                fps_start_time = time.time()

            

            cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Merge frames horizontally
            merged_frame = cv2.hconcat([frame, frame, frame])

            # pil_image=Image.fromarray(color_converted)
            pil_image=Image.fromarray(merged_frame)

            self.__camera.write_frame(pil_image.tobytes())

            time.sleep(sleep_time)

def main():
    parser = argparse.ArgumentParser()
    # parser.add_argument("-m", "--meeting", required = True, help = "Meeting URL")
    parser.add_argument("-s", "--size", required = True, help = "Size of video, L, M or S")
    parser.add_argument("-f", "--framerate", type=int, required = True, help = "Framerate")
    args = parser.parse_args()

    Daily.init()

    # app = SendImageApp(args.image, args.framerate)
    app = SendImageApp(args.size, args.framerate)

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
