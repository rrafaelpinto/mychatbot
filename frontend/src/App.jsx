import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const StreamLangchain = () => {
    // State to store the input from the user
    const [input, setInput] = useState('');
    // State to store the responses/messages
    const [responses, setResponses] = useState([]);
    // Ref to manage the WebSocket connection
    const ws = useRef(null);
    // Ref to scroll to the latest message
    const messagesEndRef = useRef(null);
    // Maximum number of attempts to reconnect
    const [reconnectAttempts, setReconnectAttempts] = useState(0);
    const maxReconnectAttempts = 5;

    // Function to setup the WebSocket connection and define event handlers
    const setupWebSocket = () => {
        ws.current = new WebSocket('ws://127.0.0.1:8000/ws/chat/');
        let ongoingStream = null; // To track the ongoing stream's ID

        ws.current.onopen = () => {
            console.log("WebSocket connected!");
            setReconnectAttempts(0); // Reset reconnect attempts on successful connection
        };

        ws.current.onmessage = (event) => {
            const data = JSON.parse(event.data);
            let sender = data.name;

            // Handle different types of events from the WebSocket
            if (data.event === 'on_parser_start') {
                // When a new stream starts
                ongoingStream = { id: data.run_id, content: '' };
                setResponses(prevResponses => [...prevResponses, { sender, message: '', id: data.run_id }]);
            } else if (data.event === 'on_parser_stream' && ongoingStream && data.run_id === ongoingStream.id) {
                // During a stream, appending new chunks of data
                setResponses(prevResponses => prevResponses.map(msg =>
                    msg.id === data.run_id ? { ...msg, message: msg.message + data.data.chunk } : msg));
            }
        };

        ws.current.onerror = (event) => {
            console.error("WebSocket error observed:", event);
        };

        ws.current.onclose = (event) => {
            console.log(`WebSocket is closed now. Code: ${event.code}, Reason: ${event.reason}`);
            handleReconnect();
        };
    };

    // Function to handle reconnection attempts with exponential backoff
    const handleReconnect = () => {
        if (reconnectAttempts < maxReconnectAttempts) {
            let timeout = Math.pow(2, reconnectAttempts) * 1000; // Exponential backoff
            setTimeout(() => {
                setupWebSocket(); // Attempt to reconnect
            }, timeout);
        } else {
            console.log("Max reconnect attempts reached, not attempting further reconnects.");
        }
    };

    // Effect hook to setup and cleanup the WebSocket connection
    useEffect(() => {
        setupWebSocket(); // Setup WebSocket on component mount

        return () => {
            if (ws.current.readyState === WebSocket.OPEN) {
                ws.current.close(); // Close WebSocket on component unmount
            }
        };
    }, []);

    // Effect hook to auto-scroll to the latest message
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [responses]);

    // Function to render each message
    const renderMessage = (response, index) => (
        <div key={index} className={`message ${response.sender}`}>
            <strong>{response.sender}</strong> <p>{response.message}</p>
        </div>
    );

    // Handler for input changes
    const handleInputChange = (e) => {
        setInput(e.target.value);
    };

    // Handler for form submission
    const handleSubmit = (e) => {
        e.preventDefault();
        const userMessage = { sender: "You", message: input };
        setResponses(prevResponses => [...prevResponses, userMessage]);
        ws.current.send(JSON.stringify({ message: input })); // Send message through WebSocket
        setInput(''); // Clear input field
    };

    return (
        <div className="chat-container">
            <div className="messages-container">
                {responses.map((response, index) => renderMessage(response, index))}
                <div ref={messagesEndRef} /> {/* Invisible element to help scroll into view */}
            </div>
            <form onSubmit={handleSubmit} className="input-form">
                <input
                    type="text"
                    value={input}
                    onChange={handleInputChange}
                    placeholder="Type your message here..."
                />
                <button type="submit">Send</button>
            </form>
        </div>
    );
};

/*export default StreamLangchain;*/
const ResumeFormatter = () => {
    const [formattedResume, setFormattedResume] = useState(null);
    const [socket, setSocket] = useState(null);
    const userId = 1; // Defina o userId fixo aqui

    const startWebSocket = () => {
        const ws = new WebSocket('ws://127.0.0.1:8000/ws/chat/');

        ws.onopen = () => {
            ws.send(JSON.stringify({ user_id: userId }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.error) {
                console.error(data.error);
            } else {
                if (data.message) {
                    console.log(data.message);
                }
                if (data.result) {
                    setFormattedResume(data.result);
                }
            }
        };

        ws.onclose = (event) => {
            console.log('WebSocket closed: ', event);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error: ', error);
        };

        setSocket(ws);
    };

    useEffect(() => {
        return () => {
            if (socket) {
                socket.close();
            }
        };
    }, [socket]);

    return (
        <div>
            <button onClick={startWebSocket}>Format Resume</button>
            {formattedResume ? (
                <div>
                    <h2>Formatted Resume</h2>
                    <pre>{JSON.stringify(formattedResume, null, 2)}</pre>
                </div>
            ) : (
                <p>Click the button to format resume...</p>
            )}
        </div>
    );
};


export default ResumeFormatter;