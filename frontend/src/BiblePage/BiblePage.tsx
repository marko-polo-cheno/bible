import { BibleChatProvider } from '../contexts/BibleChatContext';
import BibleApp from '../Bible/BibleApp';

function BiblePage() {
  return (
    <BibleChatProvider>
      <BibleApp />
    </BibleChatProvider>
  );
}

export default BiblePage;
