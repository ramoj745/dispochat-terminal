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

####### Colors #######

BLUE = "\033[94m"
RESET = "\033[0m"

####### Connection #######

def pingServer(url, retries=10, delay=3):
    print(f"Waiting for server at {url} to respond...")
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print("Connected!")
                return True
        except requests.RequestException:
            print(f"Attempt {i+1}/{retries} failed. Retrying in {delay} seconds...")
            time.sleep(delay)
    print("Server did not respond after several attempts.")
    return False

####### Socket.io ########

sio = socketio.Client()
backendURL = "https://dispochat-react-be.onrender.com"

if pingServer(backendURL): # check if backend is up
    sio.connect(backendURL) 

@sio.on("loadMessages")
def loadMessages(messages):
    for message in messages:
        print("[Past Message]:", message['message'])

@sio.on("newMessage")
def newMessage(data):
    sender = data.get("senderId")
    message = data.get("message")
    
    if sender == sio.sid:
        print(f"{Fore.CYAN}You:{Style.RESET_ALL} {message}")
    else:
        print(f"{sender}: {message}")

def sendMessage(message, roomId, senderId):
    payload = {
        "roomId": roomId,
        "senderId": senderId,
        "message": message
    }
    requests.post(f"{backendURL}/sendMessage", json=payload)


def inputLoop(roomId, clientId, roomName):
    print(f"\n----- You've entered {roomName} ------")
    print("(Type 'exit' to leave)\n")
    while True:
        try:
            message = input("")
            if not message.strip():
                print("Message cannot be blank.")
                continue  
            if message.lower() == "exit":
                print("Exiting...")
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
            print("\n\nWelcome to DispoChat! This small project allows messaging through Python terminals instead of a web interface.\nThis app uses the API from my DispoChat web project.\n(You can still chat with web users!)\n")
            print("1. Create Room")
            print("2. Join Room")
            print("3. Exit")
            print()

            choice = input("Choose an option [1-3]: ")

            if choice == "1":
                roomName = input("Type a name for your new room: ")
                password = input(f"Type a password for {roomName} (Leave blank if no password): ")
                clientId = sio.sid # socket id

                createRoom(roomName, password, clientId)

            elif choice == "2":
                roomsList = getRooms()
                print("\nHere are the list of rooms that are currently active:")
                for i, rooms in enumerate(roomsList, start=1):
                    print(f"{i}. {rooms['name']}")
                print()
                try:
                    choice = int(input(f"Choose an option [1-{len(roomsList)}]: "))
                    print()

                    if 1 <= choice <= len(roomsList):
                        selectedRoom = roomsList[choice - 1]
                        print(f"You've selected {selectedRoom['name']}\n")
                        time.sleep(0.5)
                        
                        roomId = selectedRoom['_id']
                        clientId = sio.sid
                        roomName = selectedRoom['name']

                        response = joinRoom(roomId, clientId)

                        while True:
                            if sio.connected:
                                if response['isPasswordProtected']:
                                    print("Room is password protected.")
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
                                        print(jsonData['message'])
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
                    print("Please enter a valid number.")
            elif choice == "3":
                print("\nExiting...")
                time.sleep(1.5)
                break
            else:
                print("\nPlease enter a valid number.")
                continue


if __name__ == "__main__":
    main()










