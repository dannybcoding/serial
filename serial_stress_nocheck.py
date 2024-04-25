import serial
import time
import sys

def stress_test(port1, port2, baudrate, duration_sec):
    try:
        # Open serial ports
        ser1 = serial.Serial(port1, baudrate)
        ser2 = serial.Serial(port2, baudrate)
        print(f"Serial ports {port1} and {port2} opened successfully.")

        # Get the current time
        start_time = time.time()
        end_time = start_time + duration_sec

        # Perform stress test for specified duration
        while time.time() < end_time:
            # Send data from port 1 to port 2
            ser1.write(b"Hello from port 1!\n")

            # Read data from port 2
            response = ser2.readline()
            print(f"Data received on port 2: {response.strip().decode('utf-8')}")

            # Send data from port 2 to port 1
            ser2.write(b"Hello from port 2!\n")

            # Read data from port 1
            response = ser1.readline()
            print(f"Data received on port 1: {response.strip().decode('utf-8')}")

            # Wait for a short duration between iterations
            time.sleep(0.1)

        # Close serial ports
        ser1.close()
        ser2.close()
        print(f"Serial ports {port1} and {port2} closed.")

    except serial.SerialException as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    port1 = "/dev/ttye800"  # Replace with your first COM port
    port2 = "/dev/ttyTS00"  # Replace with your second COM port
    baudrate = 9600          # Adjust baud rate as needed
    duration_sec = 60        # Duration of stress test in seconds

    stress_test(port1, port2, baudrate, duration_sec)
    sys.exit(0)
