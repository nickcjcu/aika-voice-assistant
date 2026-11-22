
const { Room, RoomEvent, Track } = LivekitClient;

let room = null;
let microphoneEnabled = true;

const messages = document.getElementById("messages");
const status = document.getElementById("status");

const connectButton = document.getElementById("connectButton");
const disconnectButton = document.getElementById("disconnectButton");
const micButton = document.getElementById("micButton");

// Store chat bubbles so incoming transcription chunks
// can update the same message instead of creating new ones.
const segmentMessages = new Map();


function updateStatus(message) {
    status.textContent = message;
}


function createMessage(sender, isUser) {

    const welcome = document.getElementById("welcome");

    if (welcome) {
        welcome.remove();
    }

    const messageContainer = document.createElement("div");

    messageContainer.className = isUser
        ? "message user"
        : "message assistant";

    const senderLabel = document.createElement("div");

    senderLabel.className = "sender";

    senderLabel.textContent = sender;

    const messageText = document.createElement("div");

    messageContainer.appendChild(senderLabel);
    messageContainer.appendChild(messageText);

    messages.appendChild(messageContainer);

    return {
        container: messageContainer,
        text: messageText
    };
}


function updateMessageBubble(key, sender, text, isUser, isFinal, firstChunk) {

    let message = segmentMessages.get(key);

    // Create a new bubble if this is a new transcription
    if (!message) {

        message = createMessage(sender, isUser);

        message.text = "";

        message.isFinal = false;

        segmentMessages.set(key, message);
    }

    // The final transcription replaces any earlier interim text
    if (isFinal && firstChunk) {

        message.text = "";

        message.isFinal = true;
    }

    // Add the latest incoming text chunk
    message.text += text;

    message.container.lastChild.textContent = message.text;

    // Automatically scroll to the latest message
    messages.scrollTop = messages.scrollHeight;

    // Keep the map from growing indefinitely
    if (segmentMessages.size > 200) {

        const oldestKey = segmentMessages.keys().next().value;

        segmentMessages.delete(oldestKey);
    }
}


async function connectAika() {

    if (room) {
        return;
    }

    try {

        connectButton.disabled = true;

        updateStatus("Connecting to AIKA+...");

        // Ask Python for a LiveKit connection token
        const response = await fetch("/token");

        const connectionInfo = await response.json();

        if (!response.ok) {

            throw new Error(
                connectionInfo.error || "Could not create LiveKit token."
            );
        }

        console.log("LiveKit URL:", connectionInfo.url);

        console.log("Room name:", connectionInfo.room);

        // Create a LiveKit room
        room = new Room();

        // Handle incoming audio from AIKA+
        room.on(
            RoomEvent.TrackSubscribed,
            (track, publication, participant) => {

                if (track.kind === Track.Kind.Audio) {

                    const audioElement = track.attach();

                    document.body.appendChild(audioElement);
                }
            }
        );

        // Remove audio when a track is unsubscribed
        room.on(
            RoomEvent.TrackUnsubscribed,
            (track) => {

                track.detach().forEach(element => element.remove());
            }
        );

        // Detect when AIKA+ joins the room
        room.on(
            RoomEvent.ParticipantConnected,
            (participant) => {

                if (participant.isAgent) {

                    updateStatus("AIKA+ is ready");

                    console.log(
                        "AIKA+ joined the room:",
                        participant.identity
                    );
                }
            }
        );

        // Receive speech transcriptions progressively
        room.registerTextStreamHandler(
            "lk.transcription",

            async (reader, participantInfo) => {

                try {

                    const attributes = reader.info?.attributes || {};

                    const isFinal =
                        attributes["lk.transcription_final"] === "true";

                    const segmentId =
                        attributes["lk.segment_id"];

                    // Identify whether the transcription belongs to the user
                    const isUser =
                        participantInfo.identity ===
                        room.localParticipant.identity;

                    const sender = isUser ? "You" : "AIKA+";

                    // Use the segment ID to keep each transcription
                    // in the same chat bubble.
                    const messageKey = participantInfo.identity + "-" +
                        (segmentId || reader.info?.id || reader.info?.streamId || Date.now());

                    let firstChunk = true;

                    // Read and display each chunk as it arrives
                    for await (const chunk of reader) {

                        if (!chunk) {
                            continue;
                        }

                        updateMessageBubble(
                            messageKey,
                            sender,
                            chunk,
                            isUser,
                            isFinal,
                            firstChunk
                        );

                        firstChunk = false;
                    }

                } catch (error) {

                    console.error("Transcription error:", error);
                }
            }
        );

        // Connect to the LiveKit room
        console.log("Attempting LiveKit room connection...");

        await room.connect(
            connectionInfo.url,
            connectionInfo.token
        );

        console.log("LiveKit room connection successful.");

        // Enable the computer microphone
        await room.localParticipant.setMicrophoneEnabled(true);

        console.log("Microphone enabled.");

        // Allow audio playback
        await room.startAudio();

        microphoneEnabled = true;

        connectButton.disabled = true;
        disconnectButton.disabled = false;
        micButton.disabled = false;

        micButton.textContent = "Mute microphone";

        updateStatus("Connected - waiting for AIKA+");

    } catch (error) {

        console.error("Connection error:", error);
        console.error("Error name:", error.name);
        console.error("Error message:", error.message);
        console.error("Error stack:", error.stack);

        console.error(
            "LiveKit connection state:",
            room ? room.state : "No room created"
        );

        updateStatus(
            "Connection failed: " +
            (error.message || error.name || "Unknown error")
        );

        connectButton.disabled = false;

        if (room) {

            await room.disconnect();

            room = null;
        }
    }
}


async function disconnectAika() {

    if (room) {

        await room.disconnect();

        room = null;
    }

    microphoneEnabled = false;

    connectButton.disabled = false;
    disconnectButton.disabled = true;
    micButton.disabled = true;

    segmentMessages.clear();

    updateStatus("Disconnected");
}


async function toggleMicrophone() {

    if (!room) {
        return;
    }

    microphoneEnabled = !microphoneEnabled;

    await room.localParticipant.setMicrophoneEnabled(
        microphoneEnabled
    );

    micButton.textContent = microphoneEnabled
        ? "Mute microphone"
        : "Unmute microphone";

    updateStatus(
        microphoneEnabled
            ? "Microphone enabled"
            : "Microphone muted"
    );
}


// Connect buttons
connectButton.addEventListener("click", connectAika);

disconnectButton.addEventListener("click", disconnectAika);

micButton.addEventListener("click", toggleMicrophone);


// Allow Python to disconnect the session when stopping the agent
window.disconnectAika = disconnectAika;
