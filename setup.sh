#!/bin/bash

set -e  # Skript se zastaví, pokud jakýkoliv příkaz selže

echo "✨ Vítejte v automatickém nastavení Ollama AI Chatbotu!"

# Funkce pro kontrolu, zda je skript spuštěn jako root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "⚠️ Tento skript potřebuje oprávnění správce (root). Spusťte ho prosím s 'sudo'."
        echo "Příklad: sudo ./setup_ai_chat.sh"
        exit 1
    fi
}
check_root

echo "📦 Krok 1/5: Aktualizace systémových balíčků..."
apt update && apt full-upgrade -y

echo "🦙 Krok 2/5: Instalace Ollama serveru..."
# Stáhneme a nainstalujeme Ollama
curl -fsSL https://ollama.com/install.sh | sh

echo "🧠 Krok 3/5: Stahování modelu 'qwen2.5-coder:1.5b' (může to chvíli trvat)..."
# Tento krok stáhne a připraví model, je to nejdelší část skriptu
ollama pull qwen2.5-coder:1.5b

echo "🌐 Krok 4/5: Nastavení webového rozhraní..."

# Vytvoříme složku pro web (pokud neexistuje)
mkdir -p /var/www/ollama-chat

# Vytvoříme soubor index.html s naším webovým chatem
cat > /var/www/ollama-chat/index.html << 'EOF'
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ollama Chat - RPi AI</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            margin: 0;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .chat-container {
            width: 100%;
            max-width: 900px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 28px;
            box-shadow: 0 25px 45px rgba(0,0,0,0.2);
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.2);
        }
        .chat-header {
            background: rgba(0,0,0,0.3);
            padding: 16px 24px;
            text-align: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .chat-header h1 { margin: 0; font-size: 1.5rem; color: white; display: flex; align-items: center; justify-content: center; gap: 10px; }
        .chat-header p { margin: 5px 0 0; font-size: 0.8rem; color: #aaa; }
        .chat-messages {
            height: 500px;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            background: rgba(0,0,0,0.2);
        }
        .message {
            display: flex;
            flex-direction: column;
            max-width: 80%;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .user { align-items: flex-end; align-self: flex-end; }
        .assistant { align-items: flex-start; align-self: flex-start; }
        .message-content {
            padding: 12px 18px;
            border-radius: 24px;
            line-height: 1.5;
            font-size: 0.95rem;
            color: white;
        }
        .user .message-content { background: #4f46e5; border-bottom-right-radius: 4px; }
        .assistant .message-content { background: rgba(255,255,255,0.15); border-bottom-left-radius: 4px; }
        .input-area {
            display: flex;
            gap: 12px;
            padding: 20px;
            background: rgba(0,0,0,0.3);
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .input-area input {
            flex: 1;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 40px;
            padding: 12px 20px;
            color: white;
            font-size: 1rem;
            outline: none;
            transition: all 0.2s;
        }
        .input-area input:focus { border-color: #4f46e5; background: rgba(255,255,255,0.15); }
        .input-area button {
            background: #4f46e5;
            border: none;
            border-radius: 40px;
            padding: 0 24px;
            color: white;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.1s, background 0.2s;
        }
        .input-area button:hover { background: #6366f1; transform: scale(1.02); }
        .input-area button:active { transform: scale(0.98); }
        .status { font-size: 0.75rem; padding: 5px 20px 10px; color: #aaa; display: flex; justify-content: space-between; }
        .typing { color: #a78bfa; font-style: italic; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); border-radius: 10px; }
        ::-webkit-scrollbar-thumb { background: #4f46e5; border-radius: 10px; }
        @media (max-width: 600px) { .message { max-width: 95%; } .chat-messages { height: 400px; } }
    </style>
</head>
<body>
<div class="chat-container">
    <div class="chat-header">
        <h1>🤖 <span>Ollama Chat (Qwen2.5-Coder 1.5B)</span> 💻</h1>
        <p>Programátorský asistent na vašem Raspberry Pi</p>
    </div>
    <div class="chat-messages" id="chatMessages">
        <div class="message assistant"><div class="message-content">👋 Ahoj! Jsem Qwen Coder, tvůj programátorský asistent. Zeptej se mě na cokoliv o kódu, Pythonu, nebo třeba VSCode!</div></div>
    </div>
    <div class="input-area">
        <input type="text" id="userInput" placeholder="Napiš zprávu... (např. 'Napiš funkci v Pythonu na seřazení seznamu')" autofocus>
        <button id="sendBtn">➤ Odeslat</button>
    </div>
    <div class="status"><span id="statusText">✅ Připraveno</span><span id="contextInfo">🧠 Kontext: posledních 5 zpráv</span></div>
</div>

<script>
    // Konfigurace API
    const OLLAMA_API_URL = 'http://localhost:11434/api/chat';
    const MODEL_NAME = 'qwen2.5-coder:1.5b';
    
    // Správa historie zpráv
    let conversationHistory = [];  // ukládá plné objekty {role, content}
    const MAX_HISTORY_PAIRS = 5;   // pamatujeme si posledních 5 párů otázka+odpověď
    
    // DOM elementy
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const statusSpan = document.getElementById('statusText');
    
    // Pomocná funkce pro přidání zprávy do UI
    function addMessageToUI(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        // jednoduché zachování mezer a odřádkování
        contentDiv.innerText = content;
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Zobrazení "píše..." indikátoru
    let typingIndicator = null;
    function showTyping() {
        removeTyping();
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant';
        typingDiv.id = 'typingIndicator';
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerText = '🤔 Píše odpověď...';
        typingDiv.appendChild(contentDiv);
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    function removeTyping() {
        const existing = document.getElementById('typingIndicator');
        if(existing) existing.remove();
    }
    
    // Odeslání zprávy do Ollama
    async function sendMessage() {
        const userMessage = userInput.value.trim();
        if(!userMessage) return;
        
        // Zablokování UI během odesílání
        sendBtn.disabled = true;
        userInput.disabled = true;
        statusSpan.innerText = '⏳ Odesílám...';
        
        // Přidání uživatelské zprávy do UI a historie
        addMessageToUI('user', userMessage);
        // Uložení do konverzační historie
        conversationHistory.push({ role: 'user', content: userMessage });
        userInput.value = '';
        
        // Nyní sestavíme kontext: Omezíme historii na MAX_HISTORY_PAIRS posledních výměn (každá výměna = user+assistant)
        // aby model nezapomínal až moc, ale zároveň nepřetěžujeme paměť RPi
        let contextMessages = [];
        // Pokud máme příliš mnoho zpráv, vezmeme jen posledních MAX_HISTORY_PAIRS*2
        if(conversationHistory.length > MAX_HISTORY_PAIRS * 2) {
            contextMessages = conversationHistory.slice(-MAX_HISTORY_PAIRS * 2);
        } else {
            contextMessages = [...conversationHistory];
        }
        
        // Volání API
        try {
            showTyping();
            statusSpan.innerText = '🧠 Model přemýšlí...';
            
            const response = await fetch(OLLAMA_API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: MODEL_NAME,
                    messages: contextMessages,
                    stream: false,
                    options: { num_ctx: 4096 }   // Zvýšení kontextu na 4096 tokenů pro lepší programování
                })
            });
            
            if(!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            
            const data = await response.json();
            const assistantReply = data.message?.content || "⚠️ Model nevrátil žádnou odpověď.";
            
            removeTyping();
            addMessageToUI('assistant', assistantReply);
            // Uložení odpovědi do historie
            conversationHistory.push({ role: 'assistant', content: assistantReply });
            
            statusSpan.innerText = '✅ Odpověď doručena';
        } catch(error) {
            console.error('Chyba:', error);
            removeTyping();
            addMessageToUI('assistant', `❌ Chyba připojení k Ollama serveru: ${error.message}. Ujistěte se, že Ollama běží (sudo systemctl status ollama).`);
            statusSpan.innerText = '⚠️ Chyba komunikace s API';
        } finally {
            sendBtn.disabled = false;
            userInput.disabled = false;
            userInput.focus();
            setTimeout(() => { if(statusSpan.innerText !== '⚠️ Chyba komunikace s API') statusSpan.innerText = '✅ Připraveno'; }, 2000);
        }
    }
    
    // Odeslání při kliknutí nebo Enter
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => { if(e.key === 'Enter') sendMessage(); });
    
    // Inicializace: kontrola dostupnosti API
    async function checkOllama() {
        try {
            const res = await fetch('http://localhost:11434/api/tags');
            if(res.ok) statusSpan.innerText = '✅ Připraveno (API OK)';
            else statusSpan.innerText = '⚠️ API nedostupné, zkontrolujte Ollamu';
        } catch(e) {
            statusSpan.innerText = '❌ Ollama API nereaguje, je spuštěné?';
        }
    }
    checkOllama();
</script>
</body>
</html>
EOF

echo "✅ Webové rozhraní bylo vytvořeno v /var/www/ollama-chat/index.html"

echo "🚀 Krok 5/5: Spouštíme služby..."

# Zajistíme, že Ollama server běží jako služba a startuje s RPi
systemctl enable ollama
systemctl restart ollama

# Počkáme pár sekund, než Ollama skutečně začne naslouchat
echo "⏳ Čekáme na spuštění Ollama serveru..."
sleep 5

# Spustíme jednoduchý HTTP server pro naše webové rozhraní na pozadí na portu 8080
cd /var/www/ollama-chat
if ! command -v python3 &> /dev/null; then
    echo "⚠️ Python3 není nainstalován, instaluji..."
    apt install python3 -y
fi

# Zabijeme případné staré procesy na portu 8080
pkill -f "python3 -m http.server 8080" 2>/dev/null || true

# Spuštění HTTP serveru na pozadí
nohup python3 -m http.server 8080 --bind 0.0.0.0 > /tmp/ollama_web.log 2>&1 &

echo ""
echo "🎉 INSTALACE DOKONČENA! 🎉"
echo ""
echo "📌 Webové rozhraní je dostupné na: http://$(hostname -I | awk '{print $1}'):8080"
echo "📌 Model Qwen2.5-Coder je stažen a Ollama běží na pozadí."
echo "📌 Kontextová paměť je nastavena na posledních 5 výměn (což je optimální pro RPi HW)."
echo "📌 API Ollama běží na: http://localhost:11434"
echo "📌 Pro ukončení HTTP serveru použij: pkill -f 'python3 -m http.server 8080'"
echo ""

# Zobrazíme status Ollamy
systemctl status ollama --no-pager
