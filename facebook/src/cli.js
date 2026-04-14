import { config } from "./config.js";
import { publishToFacebookGroup } from "./facebookPoster.js";

function parseArgs(argv) {
  const result = {
    groupUrl: config.defaultGroupUrl,
    text: "",
    imagePath: "",
    appendText: "",
    dryRun: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--group-url") {
      result.groupUrl = argv[i + 1] || "";
      i += 1;
    } else if (arg === "--text") {
      result.text = argv[i + 1] || "";
      i += 1;
    } else if (arg === "--image") {
      result.imagePath = argv[i + 1] || "";
      i += 1;
    } else if (arg === "--append-text") {
      result.appendText = argv[i + 1] || "";
      i += 1;
    } else if (arg === "--dry-run") {
      result.dryRun = true;
    }
  }

  return result;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const result = await publishToFacebookGroup(options);
  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
