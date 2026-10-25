const bcrypt = require("/usr/src/node-red/node_modules/bcryptjs");
const adminUser = process.env.NODE_RED_ADMIN_USER;
const adminPassword = process.env.NODE_RED_ADMIN_PASSWORD;
if (!adminUser || !adminPassword) {
  throw new Error("NODE_RED_ADMIN_USER and NODE_RED_ADMIN_PASSWORD are required");
}

module.exports = {
  // Node-RED otherwise loads flows_<hostname>.json and the committed flows never start.
  flowFile: "flows.json",
  credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET,
  adminAuth: {
    type: "credentials",
    users: [{
      username: adminUser,
      password: bcrypt.hashSync(adminPassword, 8),
      permissions: "*"
    }]
  }
};
