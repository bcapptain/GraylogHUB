import socket
import json
import requests
from threading import Thread
import logging
import time
import sys
from typing import Optional
import os
import traceback

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Force stdout to be line-buffered
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

class GELFForwarder:
    def __init__(self, tcp_host: str, tcp_port: int, function_url: str, buffer_size: int = 8192,
                 connection_timeout: int = 60, max_message_size: int = 1024 * 1024):  # 1MB default max
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.function_url = function_url
        self.buffer_size = buffer_size
        self.connection_timeout = connection_timeout
        self.max_message_size = max_message_size
        self.server_socket: Optional[socket.socket] = None
        # Metrics
        self.messages_processed = 0
        self.messages_failed = 0
        self.connections_handled = 0
        self.start_time = None
        self.last_metrics_time = time.time()
        self.metrics_interval = 60  # Log metrics every 60 seconds
        logger.info("GELFForwarder initialized with function URL: %s", function_url)
        
    def start(self):
        """Start the TCP server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow port reuse
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.tcp_host, self.tcp_port))
        self.server_socket.listen(5)
        
        self.start_time = time.time()
        logger.info(f"Server listening on {self.tcp_host}:{self.tcp_port}")
        
        while True:
            try:
                client_socket, address = self.server_socket.accept()
                logger.info(f"Accepted connection from {address}")
                client_thread = Thread(target=self.handle_client, args=(client_socket, address))
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")
                
    def handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle individual client connections"""
        buffer = ""
        client_socket.settimeout(self.connection_timeout)
        self.connections_handled += 1
        
        while True:
            try:
                data = client_socket.recv(self.buffer_size)
                if not data:
                    break
                
                # Decode received data
                decoded_data = data.decode('utf-8')
                
                # Add to buffer
                buffer += decoded_data
                
                # Process complete JSON objects
                while True:
                    try:
                        # Find the start of a JSON object
                        start = buffer.find('{')
                        if start == -1:
                            buffer = ""
                            break
                            
                        # Try to parse what we have
                        json.loads(buffer[start:])
                        # If successful, we have a complete message
                        self.process_message(buffer[start:], address)
                        buffer = ""
                        break
                        
                    except json.JSONDecodeError as e:
                        if "Extra data" in str(e):
                            pos = int(str(e).split('char ')[-1].strip(')'))
                            self.process_message(buffer[start:start+pos], address)
                            buffer = buffer[start+pos:]
                        else:
                            break
                
            except Exception as e:
                logger.error(f"Error handling client {address}: {e}")
                break
                
        client_socket.close()
        
    def log_metrics(self):
        """Log throughput and performance metrics"""
        current_time = time.time()
        elapsed = current_time - self.last_metrics_time
        
        if elapsed >= self.metrics_interval:
            messages_per_second = self.messages_processed / elapsed
            failure_rate = (self.messages_failed / (self.messages_processed + self.messages_failed)) * 100 if self.messages_processed + self.messages_failed > 0 else 0
            
            logger.info(f"Performance Metrics:")
            logger.info(f"Messages/second: {messages_per_second:.2f}")
            logger.info(f"Total processed: {self.messages_processed}")
            logger.info(f"Total failed: {self.messages_failed}")
            logger.info(f"Failure rate: {failure_rate:.2f}%")
            logger.info(f"Active connections: {self.connections_handled}")
            
            # Reset counters
            self.messages_processed = 0
            self.messages_failed = 0
            self.last_metrics_time = current_time

    def process_message(self, message: str, address: tuple):
        """Process and forward individual GELF messages"""
        try:
            gelf_data = json.loads(message)
            response = self.forward_to_function(gelf_data)
            
            if response.status_code not in (200, 201, 202):
                logger.error(f"Error forwarding message: HTTP {response.status_code}")
                self.messages_failed += 1
            else:
                self.messages_processed += 1
            
            # Log metrics periodically
            self.log_metrics()
                
        except json.JSONDecodeError:
            self.messages_failed += 1
        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            self.messages_failed += 1
            
    def forward_to_function(self, gelf_data: dict) -> requests.Response:
        """Forward GELF data to Azure Function"""
        retries = 3
        retry_delay = 1
        
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.function_url,
                    json=gelf_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                return response
                
            except requests.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(retry_delay * (attempt + 1))
                
    def shutdown(self):
        """Gracefully shutdown the server"""
        if self.server_socket:
            self.server_socket.close()
            logger.info("Server shutdown complete")

    def log_debug(self, message: str):
        """Helper method to ensure immediate output"""
        logger.info(message)
        print(message, flush=True)
        sys.stdout.flush()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='GELF TCP to HTTP Forwarder')
    parser.add_argument('--host', default='0.0.0.0', help='TCP server host')
    parser.add_argument('--port', type=int, default=12201, help='TCP server port')
    parser.add_argument('--function-url', 
                       default=os.environ.get('FUNCTION_URL'),
                       help='Azure Function URL (can also be set via FUNCTION_URL environment variable)')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--connection-timeout', type=int, default=60, help='Connection timeout in seconds')
    parser.add_argument('--max-message-size', type=int, default=1024*1024, help='Maximum message size in bytes')
    
    args = parser.parse_args()
    
    if not args.function_url:
        parser.error("Function URL must be provided either via --function-url argument or FUNCTION_URL environment variable")
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    forwarder = GELFForwarder(
        args.host, 
        args.port, 
        args.function_url,
        connection_timeout=args.connection_timeout,
        max_message_size=args.max_message_size
    )
    
    try:
        forwarder.start()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        forwarder.shutdown()