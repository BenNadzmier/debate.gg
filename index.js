import { GatewayIntentBits } from 'discord.js'
import dotenv from 'dotenv'
dotenv.config()

import {Client} from 'discord.js'

const client = new Client ({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.GuildMembers,
        GatewayIntentBits.DirectMessages
    ]
});

client.login(process.env.DISCORD_TOKEN);

const queues = {
    ap:[],
    //judge:[]
};

const roles = [
    "Gov 1",
    "Gov 2",
    "Gov 3",
    "Opp 1",
    "Opp 2",
    "Opp 3",
    "Judge"
];

queues.ap.push({
    userId: interaction.user.id,
    joinedAt: Date.now()
});

//queues.judge.push({
//    userId: interaction.user.id,
//    joinedAt: Date.now()
//});  

if (queues.ap.length >= 7) {
    startAPMatch();
}