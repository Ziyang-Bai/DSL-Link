import socket
import threading
import textwrap

# Global message board and terminal size defaults
messages = []
term_width = 80
term_height = 24

def negotiate_telnet(sock):
    IAC = 255
    DO = 253
    WILL = 251
    LINEMODE = 34
    SUPPRESS_GO_AHEAD = 3
    NAWS = 31
    ECHO = 1

    try:
        # Request line mode
        sock.sendall(bytes([IAC, WILL, LINEMODE]))
        # Request to suppress go ahead signal
        sock.sendall(bytes([IAC, DO, SUPPRESS_GO_AHEAD]))
        # Request window size (NAWS)
        sock.sendall(bytes([IAC, DO, NAWS]))
        # Enable server echo: server will echo back each character
        sock.sendall(bytes([IAC, WILL, ECHO]))
    except Exception as e:
        print("Telnet negotiation error:", e)

def handle_client(client_socket):
    global term_width, term_height
    negotiate_telnet(client_socket)
    
    # Wrap the socket to enable byte-level reading/writing
    client_file = client_socket.makefile('rwb', buffering=0)

    def write_line(text):
        global term_width
        # Wrap text according to current terminal width
        wrapped_lines = []
        for line in text.splitlines():
            wrapped_lines.extend(textwrap.wrap(line, width=term_width) or [''])
        for wrapped in wrapped_lines:
            # Use CR+LF for proper Telnet line breaks
            client_file.write((wrapped + "\r\n").encode('utf-8'))
        client_file.flush()

    def read_line():
        global term_width, term_height
        line = bytearray()
        IAC = 255
        SB = 250
        SE = 240
        while True:
            ch = client_file.read(1)
            if not ch:
                break  # Connection closed

            # 处理退格（Backspace）和删除键（DEL）
            if ch[0] in (8, 127):
                if len(line) > 0:
                    line = line[:-1]
                    # 发送退格序列，让客户端删除最后一个字符显示
                    client_file.write(b'\b \b')
                    client_file.flush()
                continue

            if ch[0] == IAC:
                cmd = client_file.read(1)
                if not cmd:
                    break
                if cmd[0] == IAC:
                    line.append(IAC)
                    # Echo the escaped IAC byte
                    client_file.write(ch)
                    client_file.flush()
                    continue
                if cmd[0] == SB:
                    opt = client_file.read(1)
                    if not opt:
                        break
                    if opt[0] == 31:  # NAWS
                        data = client_file.read(4)
                        if len(data) == 4:
                            term_width = int.from_bytes(data[:2], 'big')
                            term_height = int.from_bytes(data[2:], 'big')
                        # Skip until IAC SE
                        while True:
                            byte = client_file.read(1)
                            if not byte:
                                break
                            if byte[0] == IAC:
                                next_byte = client_file.read(1)
                                if next_byte and next_byte[0] == SE:
                                    break
                        continue
                    else:
                        # Skip unknown subnegotiation data
                        while True:
                            byte = client_file.read(1)
                            if not byte:
                                break
                            if byte[0] == IAC:
                                next_byte = client_file.read(1)
                                if next_byte and next_byte[0] == SE:
                                    break
                        continue
                else:
                    # Skip non-subnegotiation commands by reading an extra option byte
                    client_file.read(1)
                    continue
            elif ch in (b'\r', b'\n'):
                # Echo newline
                client_file.write(b'\r\n')
                client_file.flush()
                break
            else:
                line += ch
                # Echo normal character
                client_file.write(ch)
                client_file.flush()
        return line.decode('utf-8', errors='ignore').strip()

    # Prompt for nickname
    write_line(r"""
    ____  _____ __         __    _       __  
   / __ \/ ___// /        / /   (_)___  / /__
  / / / /\__ \/ /  ______/ /   / / __ \/ //_/
 / /_/ /___/ / /__/_____/ /___/ / / / / ,<   
/_____//____/_____/    /_____/_/_/ /_/_/|_|  
                                             
                                             
""")
    write_line("Welcome to the DSL-Link Message Board!\r\n")
    write_line("Welcome! Please enter your nickname: ")
    nickname = read_line()
    write_line(f"Hello, {nickname}!\r\n")

    while True:
        write_line("\r\nMessage Board:")
        if messages:
            for msg in messages:
                write_line(msg)
        else:
            write_line("No messages.")

        write_line("\r\nEnter your message (type 'exit' to quit): ")
        message = read_line()

        if len(message) == 0:
            write_line("Message cannot be empty. Please try again.\r\n")
            continue

        if message.lower() == 'exit':
            write_line("Thank you!\r\n")
            break
        else:
            messages.append(f"{nickname}: {message}")
            write_line("Message sent.\r\n")
    
    client_file.close()
    client_socket.close()

def start_server(host='127.0.0.1', port=23):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Telnet Server started at {host}:{port}...")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"Connection from {client_address}")
        client_thread = threading.Thread(target=handle_client, args=(client_socket,), daemon=True)
        client_thread.start()

if __name__ == '__main__':
    start_server()
