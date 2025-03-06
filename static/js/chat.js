// document.addEventListener("DOMContentLoaded", function () {
//     var chatContainer = document.getElementById("chat-container");
//     var chatOpen = document.getElementById("chat-open");
//     var chatClose = document.getElementById("chat-close");
//     var chatSend = document.getElementById("chat-send");
//     var chatInput = document.getElementById("chat-input");
//     var chatBox = document.getElementById("chat-box");

//     // Ensure elements exist
//     if (!chatContainer || !chatOpen || !chatClose || !chatSend || !chatInput || !chatBox) {
//         console.error("Chat elements not found!");
//         return;
//     }

//     // Hide chat initially
//     chatContainer.style.display = "none";

//     // Open chat
//     chatOpen.addEventListener("click", function () {
//         chatContainer.style.display = "block";
//     });

//     // Close chat
//     chatClose.addEventListener("click", function () {
//         chatContainer.style.display = "none";
//     });

//     // Send message
//     chatSend.addEventListener("click", function () {
//         sendMessage();
//     });

//     // Allow pressing "Enter" to send message
//     chatInput.addEventListener("keypress", function (event) {
//         if (event.key === "Enter" && !event.shiftKey) {
//             event.preventDefault();
//             sendMessage();
//         }
//     });

//     function sendMessage() {
//         var userMessage = chatInput.value.trim();
//         if (!userMessage) return;

//         var lessonId = chatContainer.getAttribute("data-lesson-id");
//         var csrfToken = chatContainer.getAttribute("data-csrf-token");

//         // Append user message
//         var userDiv = document.createElement("div");
//         userDiv.innerHTML = "<strong>Сіз:</strong> " + userMessage;
//         chatBox.appendChild(userDiv);

//         // Loading message
//         var loadingDiv = document.createElement("div");
//         loadingDiv.id = "loading-message";
//         loadingDiv.innerHTML = "Жүктелуде...";
//         chatBox.appendChild(loadingDiv);

//         fetch(`/lesson/${lessonId}/chat-response/`, {  
//             method: "POST",
//             headers: {
//                 "Content-Type": "application/json",
//                 "X-CSRFToken": csrfToken
//             },
//             body: JSON.stringify({ "message": userMessage })
//         })
//         .then(response => response.json())
//         .then(data => {
//             loadingDiv.remove();
//             var botDiv = document.createElement("div");
//             botDiv.innerHTML = "<strong>ChatGPT:</strong> " + data.response;
//             chatBox.appendChild(botDiv);
//         })
//         .catch(error => {
//             console.error("Қате орын алды:", error);
//             loadingDiv.innerHTML = "Қате орын алды. Қайтадан көріңіз.";
//         });

//         // Clear input field
//         chatInput.value = "";
//     }
// });
