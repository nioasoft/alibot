import { makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } from '@whiskeysockets/baileys';
import express from 'express';
import multer from 'multer';
import { readFile } from 'fs/promises';
import pino from 'pino';
import qrcode from 'qrcode-terminal';

const PORT = process.env.WA_PORT || 3001;
const GROUP_JID = process.env.WA_GROUP_JID || ''; // Set after first connection
const AUTH_DIR = './whatsapp/auth_state';

const logger = pino({ level: 'warn' });
const app = express();
const upload = multer({ dest: '/tmp/wa_uploads/' });

app.use(express.json());

let sock = null;
let isConnected = false;

// --- Baileys Connection ---

async function connectWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
        version,
        auth: state,
        logger,
        // QR handled manually via connection.update event
        browser: ['AliBot', 'Chrome', '120.0.0'],
        connectTimeoutMs: 60000,
        // Anti-ban: mimic real browser behavior
        generateHighQualityLinkPreview: false,
        syncFullHistory: false,
        markOnlineOnConnect: false,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            console.log('\n📱 Scan QR code with WhatsApp on your dedicated phone:\n');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'open') {
            isConnected = true;
            console.log('✅ WhatsApp connected!');
        }

        if (connection === 'close') {
            isConnected = false;
            const code = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = code !== DisconnectReason.loggedOut;

            if (shouldReconnect) {
                console.log('🔄 Reconnecting...');
                setTimeout(connectWhatsApp, 5000);
            } else {
                console.log('❌ Logged out. Delete auth_state and restart to re-scan QR.');
            }
        }
    });

    // Log available groups on first connect
    sock.ev.on('messaging-history.set', () => {
        listGroups();
    });
}

async function listGroups() {
    if (!sock) return;
    try {
        const groups = await sock.groupFetchAllParticipating();
        console.log('\n📋 Available WhatsApp Groups:');
        for (const [jid, group] of Object.entries(groups)) {
            console.log(`  ${group.subject} → ${jid}`);
        }
        console.log('\nSet WA_GROUP_JID env var to the group JID you want to post to.\n');
    } catch (e) {
        // Groups might not be available immediately
    }
}

// --- HTTP API ---

// Health check
app.get('/health', (req, res) => {
    res.json({
        status: isConnected ? 'connected' : 'disconnected',
        group: GROUP_JID || 'not configured',
    });
});

// List groups
app.get('/groups', async (req, res) => {
    if (!sock || !isConnected) {
        return res.status(503).json({ error: 'WhatsApp not connected' });
    }
    try {
        const groups = await sock.groupFetchAllParticipating();
        const list = Object.entries(groups).map(([jid, g]) => ({
            jid,
            name: g.subject,
            participants: g.participants?.length || 0,
        }));
        res.json({ groups: list });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// Send text message
app.post('/send', async (req, res) => {
    const { text, group_jid } = req.body;
    const targetJid = group_jid || GROUP_JID;

    if (!sock || !isConnected) {
        return res.status(503).json({ error: 'WhatsApp not connected' });
    }
    if (!targetJid) {
        return res.status(400).json({ error: 'No group JID configured. GET /groups to find it.' });
    }
    if (!text) {
        return res.status(400).json({ error: 'text is required' });
    }

    try {
        const msg = await sock.sendMessage(targetJid, { text });
        // Anti-ban: random delay after sending
        await sleep(randomDelay(2000, 5000));
        res.json({ success: true, messageId: msg.key.id });
    } catch (e) {
        console.error('Send error:', e.message);
        res.status(500).json({ error: e.message });
    }
});

// Send image with caption
app.post('/send-image', upload.single('image'), async (req, res) => {
    const { text, group_jid } = req.body;
    const targetJid = group_jid || GROUP_JID;

    if (!sock || !isConnected) {
        return res.status(503).json({ error: 'WhatsApp not connected' });
    }
    if (!targetJid) {
        return res.status(400).json({ error: 'No group JID configured' });
    }
    if (!req.file) {
        return res.status(400).json({ error: 'image file is required' });
    }

    try {
        const imageBuffer = await readFile(req.file.path);
        const msg = await sock.sendMessage(targetJid, {
            image: imageBuffer,
            caption: text || '',
        });
        // Anti-ban: random delay after sending
        await sleep(randomDelay(3000, 7000));
        res.json({ success: true, messageId: msg.key.id });
    } catch (e) {
        console.error('Send image error:', e.message);
        res.status(500).json({ error: e.message });
    }
});

// --- Helpers ---

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function randomDelay(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

// --- Start ---

app.listen(PORT, () => {
    console.log(`🚀 WhatsApp service listening on http://localhost:${PORT}`);
    console.log(`   GET  /health     — connection status`);
    console.log(`   GET  /groups     — list available groups`);
    console.log(`   POST /send       — send text message`);
    console.log(`   POST /send-image — send image + caption\n`);
    connectWhatsApp();
});
