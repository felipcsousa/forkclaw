## 2024-03-15 - Prevent Double Submission
**Failure mode:** User can submit duplicate chat messages by rapidly pressing Enter or when Enter events overlap with a pending request.
**Learning:** `useChatController.ts` did not inherently guard against concurrent optimistic runs, leading to duplicate states. Native `onKeyDown` handlers can also occasionally fire multiple times before React's `disabled` state updates propogate to the DOM.
**Prevention:** Always add explicit early-return guards (`if (isSending) return;`) at the top of controller-level action handlers that mutate state and explicitly check `disabled` or loading flags inside keyboard handlers.
