## 2024-03-15 - Prevent Double Submission
**Failure mode:** User can submit duplicate chat messages by rapidly pressing Enter or when Enter events overlap with a pending request.
**Learning:** `useChatController.ts` did not inherently guard against concurrent optimistic runs, leading to duplicate states. Native `onKeyDown` handlers can also occasionally fire multiple times before React's `disabled` state updates propogate to the DOM.
**Prevention:** Always add explicit early-return guards (`if (isSending) return;`) at the top of controller-level action handlers that mutate state and explicitly check `disabled` or loading flags inside keyboard handlers.

## 2024-03-21 - Prevent State Update After Unmount in runAsyncAction
**Failure mode:** State variables (like isSending) might not be correctly reset if an exception occurs in an inner function while updating the state, or if the component is unmounted. It may leave the state in an incorrect pending/loading state forever.
**Learning:** Using a `finally` block around async side-effects ensures loading flags are always cleared and no race-conditions occur with the state setting flag, and using a React ref guarantees synchronous checks before the DOM renders.
**Prevention:** Use a `finally` block and a React `useRef` when setting loading state that protects against double submission, ensuring it clears no matter what.

## 2024-03-24 - Prevent double-submissions in React form handlers
**Failure mode:** In React frontend components, form submission handlers (`onSubmit`) can bypass `disabled` button states if triggered via keyboard events (e.g., hitting Enter), leading to double-submissions while a request is inflight.
**Learning:** The native `disabled` attribute on a `<button type="submit">` prevents mouse clicks but may not natively stop all keyboard-triggered `onSubmit` events on the `<form>` element itself in all browser configurations or React synthetic event lifecycles.
**Prevention:** To prevent double-submissions, always include an explicit early return guard clause (e.g., `if (disabled) return;` or `if (isLoading || isCreating || isMutating) return;`) directly inside the `onSubmit` handler.
