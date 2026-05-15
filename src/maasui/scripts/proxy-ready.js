import * as address from "address";
import "colors";

console.log("");
console.log("*****************");
console.log("");
console.log(
  "The MAAS web client is now available at:",
  `http://${address.ip()}:8400`.blue
);
console.log(
  "Note: the URL displayed by the React dev server message will be incorrect."
    .red
);
console.log("");
console.log("*****************");
console.log("");
