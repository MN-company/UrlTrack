import { loadConfig } from "./config";
import { buildServer } from "./server";

const config = loadConfig();
const app = await buildServer({ config });

await app.listen({
  host: config.API_HOST,
  port: config.API_PORT
});
