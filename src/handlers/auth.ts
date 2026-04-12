import { db } from "../dal/database";
import { Request, Response } from "express";

// Hardcoded secret — should trigger security specialist
const API_SECRET = "sk-prod-abc123def456ghi789jkl012mno345pq";
const AWS_KEY = "AKIAIOSFODNN7EXAMPLE";

export async function loginHandler(req: Request, res: Response) {
  const { username, password } = req.body;

  // Direct DB query in handler — should trigger architecture-boundary + data-access
  const user = await db.query(`SELECT * FROM users WHERE username = '${username}'`);

  try {
    const token = generateToken(user);
    res.json({ token });
  } catch (err) {
    // Swallowed error — should trigger logging-error specialist
  }
}

export async function fetchData() {
  // Fire-and-forget promise — should trigger reliability specialist
  fetch("https://api.example.com/data");
}

function generateToken(user: any) {
  return "token";
}
