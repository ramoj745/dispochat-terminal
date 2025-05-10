import requests
import socketio
import time
import threading
import sys
from colorama import init, Fore, Style
init()

####### Formatter #######

def clearLastLine():
    sys.stdout.write("\033[F\033[K")

####### Connection #######

def pingServer(url, retries=10, delay=3):
    print(f"Waiting for server at {url} to respond...")
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"{Fore.GREEN}Connected!{Style.RESET_ALL}")
                return True
        except requests.RequestException:
            print(f"{Fore.YELLOW}Attempt {i+1}/{retries} failed. Retrying in {delay} seconds...{Style.RESET_ALL}")
            time.sleep(delay)
    print(f"{Fore.RED}Server did not respond after several attempts.{Style.RESET_ALL}")
    return False

####### Socket.io ########

sio = socketio.Client()
backendURL = "https://dispochat-react-be.onrender.com"

if pingServer(backendURL): # check if backend is up
    sio.connect(backendURL) 

@sio.on("loadMessages")
def loadMessages(messages):
    for message in messages:
        print(f"{Fore.CYAN}[Past Message]:{Style.RESET_ALL}", message['message'])

@sio.on("newMessage")
def newMessage(data):
    sender = data.get("senderId")
    message = data.get("message")
    
    if sender == sio.sid:
        print(f"{Fore.CYAN}You:{Style.RESET_ALL} {message}")
    else:
        print(f"{Fore.YELLOW}{sender}:{Style.RESET_ALL} {message}")

def sendMessage(message, roomId, senderId):
    payload = {
        "roomId": roomId,
        "senderId": senderId,
        "message": message
    }
    requests.post(f"{backendURL}/sendMessage", json=payload)

def inputLoop(roomId, clientId, roomName):
    print(f"\n{Fore.MAGENTA}----- You've entered {roomName} ------{Style.RESET_ALL}")
    print(f"(Type {Fore.RED}'exit'{Style.RESET_ALL} to leave)\n")

    while True:
        try:
            message = input("")
            if not message.strip():
                print(f"{Fore.RED}Message cannot be blank.{Style.RESET_ALL}")
                continue  
            if message.lower() == "exit":
                print(f"\n{Fore.RED}Exiting...{Style.RESET_ALL}")
                time.sleep(1.5)
                sio.disconnect()
                sys.exit(0)

            sendMessage(roomId, clientId, message)
            clearLastLine()
            sio.emit("newMessage", {"roomId": roomId, "senderId": clientId, "message": message})
        except KeyboardInterrupt:
            sio.disconnect()
            sys.exit(0)

####### Functions for app ########

def createRoom(roomName, password, clientId):
    payload = {
        "name": roomName,
        "password": password,
        "clientId": clientId
    }
    response = requests.post(f"{backendURL}/createRoom", json=payload)
    return response.json()


def joinRoom(roomId, clientId):
    payload = {
        "roomId": roomId,
        "clientId": clientId
    }

    response = requests.post(f"{backendURL}/joinRoom", json=payload)
    # returns a boolean value, which is used to ask the user what's the password if password is enabled
    return response.json()

def sendMessage(roomId, senderId, message):
    payload = {
        "roomId": roomId,
        "senderId": senderId,
        "message": message
    }

    response = requests.post(f"{backendURL}/sendMessage", json=payload)
    return response.json()

def leaveRoom(roomId, clientId):
    response = requests.delete(f"{backendURL}/LeaveRoom/{roomId}/user/{clientId}")
    return response.json()

def getRooms():
    response = requests.get(f"{backendURL}/getRoomList")
    return response.json()

##### Main Loop #####

def main():
        while True:
            print(f"\n\n{Fore.CYAN}Welcome to DispoChat!{Style.RESET_ALL} This small project allows messaging through Python terminals instead of a web interface.\nThis app uses the API from my DispoChat web project.\n(You can still chat with web users!){Style.RESET_ALL}\n")
            print(f"|{Fore.YELLOW}1{Style.RESET_ALL}| Create Room")
            print(f"|{Fore.YELLOW}2{Style.RESET_ALL}| Join Room")
            print(f"|{Fore.YELLOW}3{Style.RESET_ALL}| Exit")
            print()

            choice = input(f"{Fore.GREEN}Choose an option [1-3]: {Style.RESET_ALL}")

            if choice == "1":
                roomName = input("Type a name for your new room: ")
                password = input(f"Type a password for {roomName} (Leave blank if no password): ")
                clientId = sio.sid # socket id

                createRoom(roomName, password, clientId)

            elif choice == "2":
                roomsList = getRooms()
                print(f"\nHere are the list of rooms that are currently active:")
                for i, rooms in enumerate(roomsList, start=1):
                    print(f"|{Fore.YELLOW}{i}{Style.RESET_ALL}| {rooms['name']}")
                print()
                try:
                    choice = int(input(f"{Fore.GREEN}Choose an option [1-{len(roomsList)}]: {Style.RESET_ALL}"))
                    print()

                    if 1 <= choice <= len(roomsList):
                        selectedRoom = roomsList[choice - 1]
                        print(f"You've selected the room: |{Fore.YELLOW}{selectedRoom['name']}{Style.RESET_ALL}|\n")
                        time.sleep(0.5)
                        
                        roomId = selectedRoom['_id']
                        clientId = sio.sid
                        roomName = selectedRoom['name']

                        response = joinRoom(roomId, clientId)

                        while True:
                            if sio.connected:
                                if response['isPasswordProtected']:
                                    print(f"{Fore.RED}Room is password protected.{Style.RESET_ALL}")
                                    password = input("Enter password: ")

                                    payload = { # modified payload from joinRoom function
                                        "roomId": roomId,
                                        "clientId": clientId,
                                        "password": password
                                    }

                                    rawResponse = requests.post(f"{backendURL}/joinRoom", json=payload)
                                    
                                    jsonData = rawResponse.json()
                                    
                                    if jsonData.get('incorrectPassword'):
                                        print()
                                        print(f"{Fore.RED}{jsonData['message']}{Style.RESET_ALL}")
                                        continue
                                    else:
                                        sio.emit("joinRoom", roomId)
                                        inputThread = threading.Thread(target=inputLoop, args=(roomId, clientId, roomName), daemon=True)
                                        inputThread.start()
                                        
                                        try: # handle exits
                                            while inputThread.is_alive():
                                                time.sleep(0.1)
                                        except KeyboardInterrupt:
                                            sio.disconnect()
                                            sys.exit(0)
                                else: # if not password protected
                                    sio.emit("joinRoom", roomId) # emits to backend, which then expects past messages (if available) inside the room

                                    inputThread = threading.Thread(target=inputLoop, args=(roomId, clientId, roomName), daemon=True)
                                    inputThread.start()

                                    try: # handle exits
                                        while inputThread.is_alive():
                                            time.sleep(0.1)
                                    except KeyboardInterrupt:
                                        sio.disconnect()
                                        sys.exit(0)
                            else:
                                sys.exit(0)
                except ValueError:
                    print(f"{Fore.RED}Please enter a valid number.{Style.RESET_ALL}")
            elif choice == "3":
                print(f"\n{Fore.RED}Exiting...{Style.RESET_ALL}")
                time.sleep(1.5)
                break
            else:
                print(f"\n{Fore.RED}Please enter a valid number.{Style.RESET_ALL}")
                continue


if __name__ == "__main__":
    main()