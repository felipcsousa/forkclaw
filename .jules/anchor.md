## 2024-03-15 - Prevent Double Submission
**Failure mode:** User can submit duplicate chat messages by rapidly pressing Enter or when Enter events overlap with a pending request.
**Learning:** `useChatController.ts` did not inherently guard against concurrent optimistic runs, leading to duplicate states. Native `onKeyDown` handlers can also occasionally fire multiple times before React's `disabled` state updates propogate to the DOM.
**Prevention:** Always add explicit early-return guards (`if (isSending) return;`) at the top of controller-level action handlers that mutate state and explicitly check `disabled` or loading flags inside keyboard handlers.

## 2024-03-21 - Prevent State Update After Unmount in runAsyncAction
**Failure mode:** State variables (like isSending) might not be correctly reset if an exception occurs in an inner function while updating the state, or if the component is unmounted. It may leave the state in an incorrect pending/loading state forever.
**Learning:** Using a `finally` block around async side-effects ensures loading flags are always cleared and no race-conditions occur with the state setting flag, and using a React ref guarantees synchronous checks before the DOM renders.
**Prevention:** Use a `finally` block and a React `useRef` when setting loading state that protects against double submission, ensuring it clears no matter what.

## 2024-05-18 - Prevent Form Double Submission
**Failure mode:** Rapid pressing of 'Enter' or double-clicks on submit buttons while mutations are in-flight trigger concurrent duplicate API requests, sometimes resulting in duplicated state or race conditions since React's disabled state hasn't propagated to the DOM yet.
**Learning:** Native `onSubmit` handlers or form actions can occasionally fire multiple times before React's `disabled` state updates propogate to the DOM. Relying solely on `disabled` prop in the component is insufficient to prevent double submissions in async environments.
**Prevention:** Always add explicit early-return guards (`if (disabled) return;`) at the top of controller-level action handlers and component-level form `onSubmit` handlers that mutate state. Use a React `useRef` to guarantee synchronous checks before the DOM renders and track inflight requests across mutations.
