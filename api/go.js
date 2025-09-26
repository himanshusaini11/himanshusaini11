import { Redis } from "@upstash/redis";
const redis = Redis.fromEnv();

export default async function handler(req, res) {
  await redis.incr("github_profile_clicks");
  res.writeHead(302, { Location: "https://github.com/himanshusaini11" });
  res.end();
}