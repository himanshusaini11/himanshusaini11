import { Redis } from "@upstash/redis";
const redis = Redis.fromEnv();

export default async function handler(_req, res) {
  const n = await redis.get("github_profile_clicks");
  const count = Number(n || 0);

  res.setHeader("Content-Type", "application/json");
  // allow CDN caching for ~1 minute
  res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate");
  res.status(200).json({
    schemaVersion: 1,
    label: "profile clicks",
    message: String(count),
    color: "blueviolet",
    cacheSeconds: 60
  });
}