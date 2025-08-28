
A Discord bot + REST API server.  
Eagle connects to a Discord guild and exposes a web API (via Quart) for guild management:  
- Kick users  
- Add/remove roles  
- Post messages to channels  
- Soft-ban and timeout users  

---

## ✨ Features
- Runs a **Discord bot** and **Quart web API** in the same process  
- Kick users via REST endpoint  
- Add / remove roles from members  
- Soft-ban users (assigns *banned* role, strips others)  
- Timeout users for a set duration (restores roles automatically)  
- Post messages into guild channels  
- Query roles for members  

## 🌐 API Endpoints

All endpoints return JSON.

GET / → Health check

POST /api/kick/<user_id> → Kick user

GET /api/get_roles/<user_id> → Get roles for a user

POST /api/add_roles/<user_id>/<role_name> → Add role to a user

POST /api/del_roles/<user_id>/<role_name> → Remove role from a user

POST /api/post_message → Post message to channel
