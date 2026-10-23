#!/usr/bin/env node
/**
 * Write MQTT broker credentials before Node-RED starts.
 *
 * The broker node stores its user and password in flows_cred.json, which is
 * gitignored and encrypted with NODE_RED_CREDENTIAL_SECRET. This script puts
 * the references ${MQTT_USER} and ${MQTT_PASSWORD} there. Node-RED expands
 * those references from the environment when the node starts, so the password
 * is not committed and a fresh clone still connects.
 */
"use strict";

const crypto = require("crypto");
const fs = require("fs");

const flowsPath = "/data/flows.json";
const credPath = "/data/flows_cred.json";
const userRef = "${MQTT_USER}";
const passwordRef = "${MQTT_PASSWORD}";
const secret = process.env.NODE_RED_CREDENTIAL_SECRET;

if (!secret) {
  console.error("mqtt-credentials: NODE_RED_CREDENTIAL_SECRET is required");
  process.exit(1);
}
if (!process.env.MQTT_USER || !process.env.MQTT_PASSWORD) {
  console.error("mqtt-credentials: MQTT_USER and MQTT_PASSWORD are required");
  process.exit(1);
}

const flows = JSON.parse(fs.readFileSync(flowsPath, "utf8"));
const brokerIds = flows.filter((node) => node.type === "mqtt-broker").map((node) => node.id);
if (brokerIds.length === 0) {
  console.error("mqtt-credentials: no mqtt-broker node in flows.json");
  process.exit(1);
}

const key = crypto.createHash("sha256").update(secret).digest();

function decrypt(raw) {
  if (!raw.$ || typeof raw.$ !== "string") {
    return raw;
  }
  const blob = raw.$;
  const iv = Buffer.from(blob.substring(0, 32), "hex");
  const decipher = crypto.createDecipheriv("aes-256-ctr", key, iv);
  const json = decipher.update(blob.substring(32), "base64", "utf8") + decipher.final("utf8");
  return JSON.parse(json);
}

function encrypt(credentials) {
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv("aes-256-ctr", key, iv);
  const body = cipher.update(JSON.stringify(credentials), "utf8", "base64") + cipher.final("base64");
  return { $: iv.toString("hex") + body };
}

let credentials = {};
if (fs.existsSync(credPath)) {
  try {
    credentials = decrypt(JSON.parse(fs.readFileSync(credPath, "utf8")));
  } catch (err) {
    console.error("mqtt-credentials: existing credential file could not be read; writing broker entries only");
    credentials = {};
  }
}
if (!credentials || typeof credentials !== "object" || Array.isArray(credentials)) {
  credentials = {};
}
delete credentials.$;

for (const id of brokerIds) {
  const current = credentials[id] && typeof credentials[id] === "object" ? credentials[id] : {};
  current.user = userRef;
  current.password = passwordRef;
  credentials[id] = current;
}

fs.writeFileSync(credPath, JSON.stringify(encrypt(credentials), null, 4) + "\n");
console.log("mqtt-credentials: broker entries point at MQTT_USER and MQTT_PASSWORD");
