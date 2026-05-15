/**
 * Insert newlines into a string at a given point. This can be useful for text
 * that is inserted into a <pre> block.
 */
export const breakLines = (
  text?: string | null,
  breakAtSpaces = true,
  lineLength = 52
): string => {
  let chunks = [];

  // Check if text is null or undefined
  if (text == null) {
    return "";
  }
  // Check that the text includes whitespace, otherwise we'll treat it as if we
  // are not breaking at spaces.
  if (breakAtSpaces && text.includes(" ")) {
    let remainingText = text.trim();
    while (remainingText.length) {
      // Get the next chunk.
      const chunk = remainingText.slice(0, lineLength);
      // Find the position of the last space in the chunk.
      const lastSpace = chunk.lastIndexOf(" ");
      // Check if this is the last section of text.
      const isRemainder = chunk === remainingText;
      // Check if this chunk is followed by a space.
      const nextCharIsSpace =
        remainingText.slice(chunk.length, chunk.length + 1) === " ";
      let chunkLength = chunk.length;
      // Check if we should break at the last space.
      if (!isRemainder && !nextCharIsSpace && lastSpace > 0) {
        chunkLength = lastSpace + 1;
      }
      // Add the chunk.
      chunks.push(chunk.slice(0, chunkLength));
      // Remove the current chunk and trim any whitespace from the start of the
      // remainder.
      remainingText = remainingText.slice(chunkLength).trim();
    }
  } else {
    // Split the text into chunks of the provided size.
    chunks = text.match(new RegExp(`.{1,${lineLength}}`, "g")) || [];
  }
  // Trim any wrapping whitespace from the chunks and add the newlines.
  return chunks.map((chunk) => chunk.trim()).join(" \n");
};

export default breakLines;
