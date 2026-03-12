import { useCallback, useEffect, useState } from 'react';

import { APP_VIEW_DETAILS, type AppView } from '../../components/app-shell-layout';

export function useShellController({
  onNavigateToChat,
}: {
  onNavigateToChat: () => void;
}) {
  const [view, setView] = useState<AppView>('chat');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() => {
    if (
      typeof window === 'undefined' ||
      typeof window.matchMedia !== 'function'
    ) {
      return true;
    }

    return window.matchMedia('(min-width: 1024px)').matches;
  });

  useEffect(() => {
    if (
      typeof window === 'undefined' ||
      typeof window.matchMedia !== 'function'
    ) {
      return undefined;
    }

    const media = window.matchMedia('(min-width: 1024px)');
    const sync = () => setIsDesktop(media.matches);

    sync();
    media.addEventListener('change', sync);

    return () => media.removeEventListener('change', sync);
  }, []);

  const navigateTo = useCallback(
    (nextView: AppView) => {
      if (nextView === 'chat') {
        onNavigateToChat();
      }
      setView(nextView);
      setMobileNavOpen(false);
    },
    [onNavigateToChat],
  );

  return {
    activeView: APP_VIEW_DETAILS[view],
    isDesktop,
    mobileNavOpen,
    navigateTo,
    setMobileNavOpen,
    setView,
    view,
  };
}
