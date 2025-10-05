/**
 * Truncates text to a specified number of sentences
 * @param text - The text to truncate
 * @param maxSentences - Maximum number of sentences to show
 * @returns Object with truncated text and whether it was truncated
 */
export const truncateToSentences = (text: string, maxSentences: number = 2) => {
  if (!text) return { text: '', isTruncated: false };
  
  const sentences = text.split(/[.!?]+/).filter(sentence => sentence.trim().length > 0);
  
  if (sentences.length <= maxSentences) {
    return { text, isTruncated: false };
  }
  
  const truncatedSentences = sentences.slice(0, maxSentences);
  const truncatedText = truncatedSentences.join('. ') + '...';
  
  return { text: truncatedText, isTruncated: true };
};

/**
 * Truncates text to a specified character limit
 * @param text - The text to truncate
 * @param maxLength - Maximum number of characters
 * @returns Object with truncated text and whether it was truncated
 */
export const truncateToLength = (text: string, maxLength: number = 200) => {
  if (!text || text.length <= maxLength) {
    return { text, isTruncated: false };
  }
  
  const truncatedText = text.substring(0, maxLength) + '...';
  return { text: truncatedText, isTruncated: true };
};
