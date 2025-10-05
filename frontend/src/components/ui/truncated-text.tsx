import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { truncateToSentences } from '@/utils/textUtils';

interface TruncatedTextProps {
  text: string;
  maxSentences?: number;
  className?: string;
  showToggle?: boolean;
}

export const TruncatedText = ({ 
  text, 
  maxSentences = 2, 
  className = '',
  showToggle = true 
}: TruncatedTextProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  if (!text) return null;
  
  const { text: truncatedText, isTruncated } = truncateToSentences(text, maxSentences);
  const displayText = isExpanded ? text : truncatedText;
  
  if (!isTruncated && !showToggle) {
    return <span className={className}>{text}</span>;
  }
  
  return (
    <div className={className}>
      <span>{displayText}</span>
      {isTruncated && showToggle && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className="ml-2 h-auto p-0 text-primary hover:text-primary/80"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="h-3 w-3 mr-1" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3 mr-1" />
              Show more
            </>
          )}
        </Button>
      )}
    </div>
  );
};
