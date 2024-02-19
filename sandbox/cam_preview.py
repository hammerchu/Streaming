import cv2

def main():
    # Open the video capture device (camera)
    cap = cv2.VideoCapture(1)
    # cap = cv2.VideoCapture(1,cv2.CAP_DSHOW)

    # Check if the camera is opened correctly
    if not cap.isOpened():
        print("Failed to open camera")
        return
    
    

    while True:
        # Read a frame from the camera
        ret, frame = cap.read()

        if not ret:
            print("Failed to capture frame")
            break

        # Display the frame in a window called "Camera"
        cv2.imshow("Camera", frame)

        # Check for the 'q' key to quit the program
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release the video capture device and close the window
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()