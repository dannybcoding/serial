import serial
import time
import threading
import string
import random
import logging
import sys
import argparse
from logging.handlers import RotatingFileHandler

# Configure logging with rotation to avoid excessive log size
handler = RotatingFileHandler('serial_test.log', maxBytes=5*1024*1024, backupCount=2)  # 5 MB per log file, 2 backups
logging.basicConfig(handlers=[handler], level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Event to signal threads to stop
stop_event = threading.Event()

def send_data(dut_port, interval, duration_sec, sent_count, sent_data, detailed_logging):
    try:
        time.sleep(1)  # Small delay before starting to send data
        start_time = time.time()
        end_time = start_time + duration_sec
        while time.time() < end_time and not stop_event.is_set():
            random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=1))
            dut_port.write(random_string.encode())
            sent_count[dut_port.port] += len(random_string)
            if detailed_logging:
                sent_data[dut_port.port].append(random_string)
                logging.debug(f"Sent: '{random_string}' from {dut_port.port} at {time.time() - start_time:.2f} seconds")
            time.sleep(interval)
    except Exception as e:
        logging.error(f"Error in send_data thread: {e}")
        stop_event.set()
    finally:
        time.sleep(2)
        dut_port.close()

def receive_data(aux_port, duration_sec, received_count, received_data, detailed_logging):
    try:
        time.sleep(1)  # Small delay before starting to receive data
        start_time = time.time()
        end_time = start_time + duration_sec + 5
        while time.time() < end_time and not stop_event.is_set():
            aux_port.timeout = 2  # Increased timeout to 2 seconds
            received_chunk = aux_port.read(aux_port.in_waiting or 1)
            
            if not received_chunk:
                logging.warning(f"Timeout: No data received from {aux_port.port} at {time.time() - start_time:.2f} seconds")
                continue
            
            received_count[aux_port.port] += len(received_chunk)
            if detailed_logging:
                received_data[aux_port.port].append(received_chunk.decode('utf-8'))
                logging.debug(f"Received: '{received_chunk.decode('utf-8')}' at {aux_port.port} at {time.time() - start_time:.2f} seconds")
    except Exception as e:
        logging.error(f"Error in receive_data thread: {e}")
        stop_event.set()
    finally:
        time.sleep(2)
        aux_port.close()

def compare_data(sent_data, received_data, port_mapping):
    logging.info("Comparing sent and received data:")

    for dut_port, aux_port in port_mapping.items():
        if dut_port in sent_data and aux_port in received_data:
            sent_str = ''.join(sent_data[dut_port])
            received_str = ''.join(received_data[aux_port])
            logging.debug(f"Port {dut_port} (Sent) -> Port {aux_port} (Received), Sent: {sent_str}, Received: {received_str}")
            if sent_str == received_str:
                logging.info(f"Data match for ports {dut_port} and {aux_port}")
            else:
                logging.info(f"Data mismatch for ports {dut_port} and {aux_port}")
                logging.info(f"Sent: {sent_str}")
                logging.info(f"Received: {received_str}")
        else:
            logging.error(f"Ports {dut_port} or {aux_port} not found in data")

def stress_test(dut_ports, aux_ports, baudrate, duration_sec, detailed_logging):
    if baudrate <= 300:
        interval = 0.25  # Increase interval for low baud rates
    elif baudrate <= 1200:
        interval = 0.05  # Medium interval for mid-range baud rates
    else:
        interval = 0.01  # Default interval for higher baud rates

    port_mapping = dict(zip(dut_ports, aux_ports))
    threads = []
    sent_count = {port: 0 for port in dut_ports}
    received_count = {port: 0 for port in aux_ports}
    sent_data = {port: [] for port in dut_ports} if detailed_logging else {}
    received_data = {port: [] for port in aux_ports} if detailed_logging else {}
    dropped_chars_count = {port: 0 for port in aux_ports}

    try:
        for dut_port_name, aux_port_name in port_mapping.items():
            try:
                logging.debug(f"Attempting to open DUT port: {dut_port_name}")
                logging.debug(f"Attempting to open AUX port: {aux_port_name}")
                dut_ser = serial.Serial(dut_port_name, baudrate, timeout=2, write_timeout=2, xonxoff=False)
                aux_ser = serial.Serial(aux_port_name, baudrate, timeout=2, write_timeout=2, xonxoff=False)
                logging.debug(f"Successfully opened DUT port: {dut_port_name}")
                logging.debug(f"Successfully opened AUX port: {aux_port_name}")

                t1 = threading.Thread(target=send_data, args=(dut_ser, interval, duration_sec, sent_count, sent_data, detailed_logging))
                t1.daemon = True
                threads.append(t1)
                t1.start()

                t2 = threading.Thread(target=receive_data, args=(aux_ser, duration_sec, received_count, received_data, detailed_logging))
                t2.daemon = True
                threads.append(t2)
                t2.start()

            except Exception as e:
                logging.error(f"Error opening serial ports: {e}")
                stop_event.set()
                break

        for thread in threads:
            thread.join()

        stop_event.set()  # Signal threads to stop

        # Calculate dropped characters
        for dut_port, aux_port in port_mapping.items():
            dropped_chars = sent_count[dut_port] - received_count[aux_port]
            dropped_chars_count[aux_port] = dropped_chars if dropped_chars > 0 else 0

        logging.info("Sent characters:")
        for port, count in sent_count.items():
            logging.info(f"{port}: {count}")

        logging.info("Received characters:")
        for port, count in received_count.items():
            logging.info(f"{port}: {count}")

        logging.info("Dropped characters:")
        for port, count in dropped_chars_count.items():
            logging.info(f"{port}: {count}")

        if detailed_logging:
            compare_data(sent_data, received_data, port_mapping)

	#Clear sent and recieved datas to avoid memory bloat
        sent_data.clear()
        received_data.clear()

        # Check if there are dropped characters
        if any(count > 0 for count in dropped_chars_count.values()):
            logging.error("Dropped characters detected. Stopping test.")
            return False  # Indicate that dropped characters were detected

    except Exception as e:
        logging.error(f"Error in stress_test function: {e}")
        return False  # Indicate that an error occurred

    return True  # Indicate that the test passed without dropping characters

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Serial Stress Test')
    parser.add_argument('duration_sec', type=int, help='Duration of the test in seconds')
    parser.add_argument('baudrate', type=int, help='Baud rate for the serial communication')
    parser.add_argument('--detailed_logging', action='store_true', help='Enable detailed logging of sent and received characters')
    parser.add_argument('--iterations', type=int, default=1, help='Number of iterations to run the test')
    parser.add_argument('--continuous', action='store_true', help='Run continuous iterations until a failure is detected')

    args = parser.parse_args()

    # List of valid baud rates
    valid_baudrates = [50, 75, 110, 300, 600, 1200, 9600, 14400, 19200, 28800, 57600, 115200, 230400]

    # Validate the baud rate
    if args.baudrate not in valid_baudrates:
        sys.exit(f"Error: Invalid baud rate. Valid baud rates are: {', '.join(map(str, valid_baudrates))}")

    dut_ports = ["/dev/ttye800", "/dev/ttye801", "/dev/ttye802", "/dev/ttye803"]
    aux_ports = ["/dev/ttyTS00", "/dev/ttyTS01", "/dev/ttyTS02", "/dev/ttyTS03"]

    iteration = 0
    try:
        while True:
            iteration += 1
            logging.info(f"Starting iteration {iteration}")
            stop_event.clear()  # Clear the stop event before each iteration

            try:
                if not stress_test(dut_ports, aux_ports, args.baudrate, args.duration_sec, args.detailed_logging):
                    logging.error("Test stopped due to error or dropped characters.")
                    break
            except Exception as e:
                logging.error(f"Iteration {iteration} failed: {e}")
                break

            logging.info(f"Finished iteration {iteration}")

            if not args.continuous and iteration >= args.iterations:
                logging.info("Completed the specified number of iterations.")
                break

    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt detected. Stopping test.")
        stop_event.set()

    logging.info("Test Completed")

        # Clear sent and received data to avoid memory bloat
        #sent_data.clear()
        #received_data.clear()

        #if stop_event.is_set():
            #logging.info("Stopping stress test due to error.")
            #break
