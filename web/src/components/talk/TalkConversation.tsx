import { ArrowLeft, ExternalLink, Info, Send, Trash2 } from 'lucide-react';
import { useLayoutEffect, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useClearTalk, useSendTalkMessage, useTalkConversation } from '@/hooks';
import { errorMessage, errorStatus, talkErrorCode } from '@/lib/api';
import { formatYear } from '@/lib/format';
import { TALK_MESSAGE_MAX } from '@/lib/schemas/talk';
import type { Speaker, TalkMessage } from '@/lib/schemas/talk';
import { entityPagePath, talkPath } from '@/lib/site-links';
import { allowanceNotice, isOptimistic, lifeText } from '@/lib/talk';
import { cn } from '@/lib/utils';
import { SpeakerAvatar } from './SpeakerAvatar';

const link = 'underline-offset-2 hover:text-foreground hover:underline';

/** "Author · CC BY-SA 4.0 · Wikimedia Commons" for the portrait, linked where it can be. */
function PortraitCredit({ speaker }: { speaker: Speaker }) {
  const img = speaker.image;
  if (!img) return null;
  const host = (() => {
    try {
      return new URL(img.page_url ?? img.url).hostname.replace(/^(www|upload|commons)\./, '');
    } catch {
      return 'source';
    }
  })();
  return (
    <span className="text-[10.5px] text-muted-foreground">
      Portrait: {img.author && <>{img.author} · </>}
      {img.license &&
        (img.license_url ? (
          <a href={img.license_url} target="_blank" rel="noopener noreferrer license" className={link}>
            {img.license}
          </a>
        ) : (
          img.license
        ))}
      {img.license && ' · '}
      <a href={img.page_url ?? img.url} target="_blank" rel="noopener noreferrer" className={link}>
        {host}
      </a>
    </span>
  );
}

function Header({
  speaker,
  knowledgeYear,
  canClear,
  onClear,
  clearing,
}: {
  speaker: Speaker;
  knowledgeYear: number | null;
  canClear: boolean;
  onClear: () => void;
  clearing: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  const life = lifeText(speaker);
  return (
    <header className="border-b bg-card/60 px-3 py-3 md:px-5">
      <div className="flex items-center gap-3">
        <Link
          to={talkPath()}
          aria-label="Back to your conversations"
          className="grid size-8 flex-none place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground md:hidden"
        >
          <ArrowLeft size={18} />
        </Link>
        <SpeakerAvatar speaker={speaker} className="size-12" />
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-heading text-[18px] font-semibold leading-tight">{speaker.name}</h2>
          <p className="flex flex-wrap items-center gap-x-3 text-[12px] text-muted-foreground">
            {life && <span className="font-mono">{life}</span>}
            <Link to={entityPagePath(speaker.id)} className={cn('inline-flex items-center gap-1', link)}>
              In the atlas <ExternalLink size={11} />
            </Link>
          </p>
        </div>
        {canClear &&
          (confirming ? (
            <div role="alertdialog" aria-label="Delete conversation" className="flex items-center gap-1.5 text-[12px]">
              <span className="hidden sm:inline">Forget this conversation?</span>
              <button
                type="button"
                disabled={clearing}
                onClick={() => {
                  onClear();
                  setConfirming(false);
                }}
                className="h-7 rounded-md bg-destructive/10 px-2.5 font-medium text-destructive hover:bg-destructive/20"
              >
                Delete
              </button>
              <button type="button" onClick={() => setConfirming(false)} className="h-7 rounded-md px-2 text-muted-foreground hover:bg-muted">
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              title="Delete this conversation"
              aria-label="Delete this conversation"
              className="grid size-8 flex-none place-items-center rounded-lg text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            >
              <Trash2 size={15} />
            </button>
          ))}
      </div>
      <p className="mt-2.5 flex items-start gap-1.5 text-[11.5px] leading-snug text-muted-foreground">
        <Info size={12} className="mt-px flex-none" />
        <span>
          AI role-play based on atlas data, not real quotations.
          {knowledgeYear != null && <> {speaker.name.split(/[\s,]/)[0]} knows nothing after {formatYear(knowledgeYear)}.</>}{' '}
          <PortraitCredit speaker={speaker} />
        </span>
      </p>
    </header>
  );
}

function Bubble({ message, name }: { message: TalkMessage; name: string }) {
  const mine = message.role === 'user';
  return (
    <div className={cn('flex', mine ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-[14px] leading-relaxed md:max-w-[70%]',
          mine ? 'rounded-br-md bg-primary text-primary-foreground' : 'rounded-bl-md border bg-card',
          isOptimistic(message) && 'opacity-70',
        )}
      >
        {!mine && <span className="mb-0.5 block text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">{name.split(/[\s,]/)[0]}</span>}
        {message.content}
      </div>
    </div>
  );
}

function Typing({ name }: { name: string }) {
  return (
    <div className="flex justify-start" role="status" aria-live="polite">
      <div className="rounded-2xl rounded-bl-md border bg-card px-3.5 py-2.5 text-[13px] text-muted-foreground">
        <span className="animate-pulse motion-reduce:animate-none">{name.split(/[\s,]/)[0]} is writing…</span>
      </div>
    </div>
  );
}

/** The chat with one person: header, messages, input. */
export function TalkConversation({ entityId }: { entityId: string }) {
  const { data, isLoading, error } = useTalkConversation(entityId);
  const send = useSendTalkMessage(entityId);
  const clear = useClearTalk(entityId);
  const navigate = useNavigate();
  const [draft, setDraft] = useState('');
  const [sendError, setSendError] = useState<{ text: string; code: string | null } | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  // Keep the newest message in view.
  const count = data?.messages.length ?? 0;
  useLayoutEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [count, send.isPending, entityId]);

  if (isLoading) return <div className="grid flex-1 place-items-center text-[13px] text-muted-foreground">Loading…</div>;

  if (error || !data) {
    const refused = errorStatus(error) === 422;
    return (
      <div className="grid flex-1 place-items-center px-6 text-center">
        <div className="max-w-sm">
          <p className="font-heading text-[18px] font-semibold">{refused ? 'This person cannot be talked to' : 'Could not open the conversation'}</p>
          <p className="mt-2 text-[13px] text-muted-foreground">
            {refused
              ? 'Only people who died long ago can be talked to. Living and recently dead people are never role-played.'
              : errorMessage(error)}
          </p>
          <Link to={talkPath()} className="mt-4 inline-block text-[13px] underline underline-offset-2">
            Back to your conversations
          </Link>
        </div>
      </div>
    );
  }

  const { entity, messages, daily } = data;
  const first = entity.name.split(/[\s,]/)[0];
  const notice = allowanceNotice(daily);
  const blocked = daily.remaining <= 0;
  const hasSaved = messages.some((m) => !isOptimistic(m));

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const text = draft.trim();
    if (!text || send.isPending || blocked) return;
    setSendError(null);
    setDraft('');
    send.mutate(text, {
      onError: (err) => {
        setDraft(text);
        setSendError({ text: errorMessage(err), code: talkErrorCode(err) });
      },
    });
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <>
      <Header
        speaker={entity}
        knowledgeYear={data.knowledge_year}
        canClear={hasSaved}
        clearing={clear.isPending}
        onClear={() => clear.mutate(undefined, { onSuccess: () => navigate(talkPath()) })}
      />

      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-3 py-4 md:px-5">
        <div className="mx-auto flex max-w-[760px] flex-col gap-3">
          {messages.length === 0 && !send.isPending && (
            <div className="mx-auto max-w-sm py-10 text-center">
              <SpeakerAvatar speaker={entity} className="mx-auto size-20 text-[26px]" />
              <p className="mt-3 font-heading text-[18px] font-semibold">Say hello to {first}</p>
              <p className="mt-1 text-[13px] text-muted-foreground">
                {first} will remember you. Ask about their life, their enemies and friends, the world they knew.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {['Who are you?', 'What troubles you most these days?', 'Who are your enemies?'].map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => {
                      setDraft(q);
                      input.current?.focus();
                    }}
                    className="rounded-full border bg-card px-3 py-1 text-[12px] hover:bg-muted"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <Bubble key={m.id} message={m} name={entity.name} />
          ))}
          {send.isPending && <Typing name={entity.name} />}
        </div>
      </div>

      <div className="border-t bg-card/60 px-3 py-3 md:px-5">
        <div className="mx-auto max-w-[760px]">
          {sendError && (
            <p role="alert" className="mb-2 rounded-lg bg-destructive/10 px-3 py-2 text-[12.5px] text-destructive">
              {sendError.text}
            </p>
          )}
          {notice && !sendError && (
            <p
              role="status"
              className={cn(
                'mb-2 rounded-lg px-3 py-2 text-[12.5px]',
                notice.tone === 'blocked' ? 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200' : 'bg-muted text-muted-foreground',
              )}
            >
              {notice.text}
            </p>
          )}
          <form onSubmit={submit} className="flex items-end gap-2">
            <textarea
              ref={input}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKey}
              disabled={blocked}
              rows={1}
              maxLength={TALK_MESSAGE_MAX}
              placeholder={blocked ? 'Come back tomorrow' : `Message ${first}…`}
              aria-label={`Message ${entity.name}`}
              className="max-h-40 min-h-10 w-full flex-1 resize-none rounded-xl border bg-background px-3 py-2 text-[14px] outline-none transition-colors [field-sizing:content] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={!draft.trim() || send.isPending || blocked}
              aria-label="Send"
              className="grid size-10 flex-none place-items-center rounded-xl bg-primary text-primary-foreground transition-colors hover:bg-primary/85 disabled:opacity-40"
            >
              <Send size={16} />
            </button>
          </form>
          {draft.length > TALK_MESSAGE_MAX * 0.8 && (
            <p className="mt-1 text-right font-mono text-[10.5px] text-muted-foreground">
              {draft.length} / {TALK_MESSAGE_MAX}
            </p>
          )}
        </div>
      </div>
    </>
  );
}
