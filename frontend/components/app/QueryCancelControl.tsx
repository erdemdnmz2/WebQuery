import { StopIcon } from '@phosphor-icons/react';
import type { useQueryCancellation } from '../../lib/query-cancellation';
import { Button } from '../ui/Button';

export function QueryCancelControl({
  cancellation,
  size = 'md',
}: {
  cancellation: ReturnType<typeof useQueryCancellation>;
  size?: 'sm' | 'md' | 'lg';
}) {
  return (
    <div className="flex flex-col items-end gap-1.5">
      <Button
        variant="secondary"
        size={size}
        icon={<StopIcon size={14} />}
        loading={cancellation.pending}
        disabled={cancellation.requested}
        onClick={() => void cancellation.cancel()}
      >
        {cancellation.pending || cancellation.requested ? 'İptal ediliyor…' : 'İptal et'}
      </Button>
      {cancellation.error && (
        <p role="alert" className="max-w-xs text-[12px] text-danger">
          {cancellation.error}
        </p>
      )}
      {cancellation.requested && (
        <span role="status" className="sr-only">Sorgunun hedef veritabanında durması bekleniyor.</span>
      )}
    </div>
  );
}
