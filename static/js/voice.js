(function () {
    const data = JSON.parse(document.getElementById("voice-data").textContent);
    const catalog = data.questions || {};
    let questions = [];
    const welcome = document.getElementById("welcomeState");
    const interview = document.getElementById("interviewState");
    const questionNum = document.getElementById("questionNum");
    const questionTotal = document.getElementById("questionTotal");
    const questionText = document.getElementById("questionText");
    const speakingBubble = document.getElementById("speakingBubble");
    const startBtn = document.getElementById("startInterviewBtn");
    const recordBtn = document.getElementById("recordBtn");
    const submitBtn = document.getElementById("submitBtn");
    const endBtn = document.getElementById("endInterviewBtn");
    const status = document.getElementById("recordingStatus");
    const transcript = document.getElementById("liveTranscript");
    const aiReply = document.getElementById("aiReply");
    const aiReplyText = document.getElementById("aiReplyText");
    const feedbackSection = document.getElementById("feedbackSection");
    const getFeedbackArea = document.getElementById("getFeedbackArea");
    const feedbackContent = document.getElementById("feedbackContent");
    const feedbackSubject = document.getElementById("feedbackSubject");
    const feedbackText = document.getElementById("feedbackText");
    const improvementText = document.getElementById("improvementText");
    const scoreValue = document.getElementById("scoreValue");
    const scoreCircle = document.getElementById("scoreCircle");
    const voiceError = document.getElementById("voiceError");
    const welcomeMic = document.getElementById("welcomeMic");

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let topic = "";
    let index = 0;
    let turns = [];
    let started = false;
    let listening = false;
    let recognition = null;
    let finalText = "";
    let speaking = null;

    questionTotal.textContent = "0";

    document.querySelectorAll(".subject-btn").forEach(function (button) {
        button.addEventListener("click", function () {
            selectTopic(button.dataset.subject, button);
        });
    });

    welcomeMic.addEventListener("click", function () {
        statusHint("Select a topic from the sidebar to begin");
    });
    startBtn.addEventListener("click", startInterview);
    recordBtn.addEventListener("click", toggleListen);
    submitBtn.addEventListener("click", submitAnswer);
    endBtn.addEventListener("click", finishInterview);
    document.getElementById("getFeedbackBtn").addEventListener("click", loadFeedback);
    document.getElementById("newInterviewBtn").addEventListener("click", resetPractice);
    transcript.addEventListener("input", syncSubmit);

    function selectTopic(name, button) {
        stopListen();
        window.speechSynthesis && window.speechSynthesis.cancel();
        topic = name;
        questions = catalog[name] || [];
        questionTotal.textContent = String(questions.length);
        index = 0;
        turns = [];
        started = false;
        finalText = "";
        document.querySelectorAll(".subject-btn").forEach(function (item) {
            item.classList.toggle("active", item === button);
        });
        welcome.classList.add("hidden");
        interview.classList.remove("hidden");
        feedbackSection.classList.add("hidden");
        feedbackContent.classList.add("hidden");
        getFeedbackArea.classList.remove("hidden");
        aiReply.classList.add("hidden");
        transcript.value = "";
        voiceError.textContent = "";
        showQuestion();
        setStatus("Microphone ready — click to listen");
        startBtn.classList.remove("hidden");
        recordBtn.classList.remove("hidden");
        submitBtn.classList.add("hidden");
        endBtn.disabled = true;
        recordBtn.disabled = false;
    }

    function showQuestion() {
        const total = questions.length;
        questionNum.textContent = String(Math.min(index + 1, total));
        questionText.textContent = questions[index] || "No questions found in candidate_answers.xlsx.";
        recordBtn.disabled = !questions[index];
    }

    function startInterview() {
        if (!questions.length) {
            setStatus("No questions found in candidate_answers.xlsx.");
            return;
        }
        started = true;
        endBtn.disabled = false;
        startBtn.classList.add("hidden");
        submitBtn.classList.remove("hidden");
        speak(questions[index], function () {
            setStatus("Microphone ready — click to listen");
        });
    }

    function toggleListen() {
        if (!topic) {
            statusHint("Select a topic from the sidebar to begin");
            return;
        }
        if (!started) {
            startInterview();
            return;
        }
        if (listening) {
            stopListen();
            return;
        }
        if (!SpeechRecognition) {
            setStatus("Speech recognition needs Chrome or Edge. You can type your answer in the transcript.");
            transcript.focus();
            return;
        }
        finalText = transcript.value.trim();
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";
        recognition.onresult = function (event) {
            let interim = "";
            let spoken = "";
            for (let i = 0; i < event.results.length; i += 1) {
                const piece = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    spoken += piece + " ";
                } else {
                    interim += piece;
                }
            }
            const prefix = finalText ? finalText + " " : "";
            transcript.value = (prefix + spoken + interim).replace(/\s+/g, " ").trim();
            syncSubmit();
        };
        recognition.onerror = function () {
            stopListen();
            setStatus("The microphone could not be used. You can type your answer in the transcript.");
        };
        recognition.onend = function () {
            if (listening) {
                try {
                    recognition.start();
                } catch (error) {
                    stopListen();
                }
            }
        };
        listening = true;
        recordBtn.classList.add("recording-active");
        recordBtn.setAttribute("aria-pressed", "true");
        setStatus("Listening…");
        try {
            recognition.start();
        } catch (error) {
            stopListen();
            setStatus("The microphone could not be used. You can type your answer in the transcript.");
        }
    }

    function stopListen() {
        listening = false;
        if (recognition) {
            recognition.onend = null;
            try {
                recognition.stop();
            } catch (error) {
                /* already stopped */
            }
        }
        recordBtn.classList.remove("recording-active");
        recordBtn.setAttribute("aria-pressed", "false");
        if (topic && started) {
            setStatus(transcript.value.trim() ? "Click Submit Answer when you are done" : "Microphone ready — click to listen");
        }
        syncSubmit();
    }

    function submitAnswer() {
        const answer = transcript.value.trim();
        if (!answer || !questions[index]) {
            setStatus("Speak or type an answer first.");
            return;
        }
        stopListen();
        const question = questions[index];
        turns.push({ question: question, answer: answer });
        submitBtn.disabled = true;
        setStatus("Reading your answer…");
        postJson("/api/voice/reply", {
            topic: topic,
            question: question,
            answer: answer,
        }).then(function (payload) {
            aiReply.classList.remove("hidden");
            aiReplyText.textContent = payload.reply;
            speak(payload.reply, advance);
        }).catch(function (error) {
            voiceError.textContent = error.message;
            advance();
        });
    }

    function advance() {
        submitBtn.disabled = false;
        transcript.value = "";
        finalText = "";
        index += 1;
        if (index >= questions.length) {
            finishInterview();
            return;
        }
        showQuestion();
        speak(questions[index], function () {
            setStatus("Microphone ready — click to listen");
        });
    }

    function finishInterview() {
        stopListen();
        window.speechSynthesis && window.speechSynthesis.cancel();
        recordBtn.disabled = true;
        submitBtn.disabled = true;
        endBtn.disabled = true;
        feedbackSection.classList.remove("hidden");
        getFeedbackArea.classList.remove("hidden");
        feedbackContent.classList.add("hidden");
        setStatus("Interview completed");
    }

    function loadFeedback() {
        if (!turns.length) {
            voiceError.textContent = "Answer at least one question before asking for feedback.";
            return;
        }
        voiceError.textContent = "";
        setStatus("Preparing feedback…");
        postJson("/api/voice/feedback", { topic: topic, turns: turns }).then(function (payload) {
            const score = Number(payload.score) || 0;
            feedbackSubject.textContent = topic;
            feedbackText.textContent = payload.feedback || "";
            improvementText.textContent = payload.improvement || "";
            scoreValue.textContent = String(score);
            const length = 2 * Math.PI * 40;
            scoreCircle.style.strokeDasharray = String(length);
            scoreCircle.style.strokeDashoffset = String(length * (1 - score / 5));
            getFeedbackArea.classList.add("hidden");
            feedbackContent.classList.remove("hidden");
            setStatus("Feedback ready");
        }).catch(function (error) {
            voiceError.textContent = error.message;
        });
    }

    function resetPractice() {
        stopListen();
        window.speechSynthesis && window.speechSynthesis.cancel();
        topic = "";
        index = 0;
        turns = [];
        started = false;
        transcript.value = "";
        aiReply.classList.add("hidden");
        interview.classList.add("hidden");
        welcome.classList.remove("hidden");
        document.querySelectorAll(".subject-btn").forEach(function (item) {
            item.classList.remove("active");
        });
        voiceError.textContent = "";
    }

    function speak(text, onend) {
        if (speaking) {
            speaking.onend = null;
            speaking.onerror = null;
            speaking = null;
        }
        if (!window.speechSynthesis || !text) {
            speakingBubble.classList.add("hidden");
            if (onend) onend();
            return;
        }
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1;
        speaking = utterance;
        speakingBubble.classList.remove("hidden");
        utterance.onend = function () {
            speaking = null;
            speakingBubble.classList.add("hidden");
            if (onend) onend();
        };
        utterance.onerror = utterance.onend;
        window.speechSynthesis.speak(utterance);
    }

    function syncSubmit() {
        submitBtn.disabled = !transcript.value.trim();
    }

    function setStatus(text) {
        status.textContent = text;
    }

    function statusHint(text) {
        const note = document.getElementById("welcomeHint");
        if (note) note.textContent = text;
    }

    function postJson(url, body) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        }).then(function (response) {
            return response.json().then(function (payload) {
                if (!response.ok) {
                    throw new Error(payload.error || "The interview assistant could not respond.");
                }
                return payload;
            });
        });
    }
})();
