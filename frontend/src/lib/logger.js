/**
 * Dev-only logger. In production all calls are no-ops.
 * Usage: import logger from "@/lib/logger";
 *        logger.error("Something went wrong", err);
 */
const isDev = process.env.NODE_ENV === "development";

const logger = {
  log:   (...args) => { if (isDev) console.log(...args); },
  warn:  (...args) => { if (isDev) console.warn(...args); },
  error: (...args) => { if (isDev) console.error(...args); },
};

export default logger;
