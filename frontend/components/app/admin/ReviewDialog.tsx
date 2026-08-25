import React, { useRef, useState } from 'react';
import { CheckIcon, EyeIcon, ProhibitIcon, ShareNetworkIcon } from '@phosphor-icons/react';
import { APPROVAL_CONFLICT, ApiError, api, errorMessage } from '../../../services/api';
import { formatCount } from '../../../lib/format';
import { Badge } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { DataGrid } from '../../ui/DataGrid';
import { Dialog } from '../../ui/Dialog';
import { EmptyState } from '../../ui/EmptyState';
import { Field } from '../../ui/Field';
import { Textarea } from '../../ui/Input';
import { useToast } from '../../ui/Toast';
import { CodeEditor } from '../CodeEditor';
import type { PendingQuery, PreviewResponse } from '../../../types';

/** Mirrors the RejectRequest Pydantic field so the server never has to refuse. */
const REASON_MIN = 3;
const REASON_MAX = 500;

export interface ReviewDialogProps {
  request: PendingQuery | null;
  onClose: () => void;
  onDecided: () => void;
}

const FACTS: { label: string; get: (request: PendingQuery) => string }[] = [
  { label: 'Talep eden', get: (request) => request.username },
  { label: 'Sunucu', get: (request) => request.servername || 'Bilinmiyor' },
  { label: 'Veritabanı', get: (request) => request.database },
];

/**
 * The approval decision surface. A reviewer sees who asked, where it runs,
 * why it was flagged and, optionally, what it actually returns before
 * choosing between three outcomes.
 */
export const ReviewDialog: React.FC<ReviewDialogProps> = ({ request, onClose, onDecided }) => {
  const toast = useToast();
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState<string | null>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);

  const previewRows = preview?.data ?? [];
  /* The service reports its row cap in the message, not as a flag. */
  const previewTruncated = /truncated/i.test(preview?.message ?? '');

  const runPreview = async () => {
    if (!request) return;
    setPreviewing(true);
    setPreviewError(null);
    try {
      setPreview(await api.previewQuery(request.workspace_id));
    } catch (caught) {
      setPreviewError(errorMessage(caught));
    } finally {
      setPreviewing(false);
    }
  };

  const resetDecisionState = () => {
    setPreview(null);
    setPreviewError(null);
    setReason('');
    setReasonError(null);
  };

  const decide = async (action: 'reject' | 'approve' | 'approve-share') => {
    if (!request) return;

    const trimmedReason = reason.trim();
    if (action === 'reject' && trimmedReason.length < REASON_MIN) {
      // Caught here rather than at the server so the reviewer keeps what they
      // typed and lands on the field that needs work.
      setReasonError(`Red gerekçesi en az ${REASON_MIN} karakter olmalıdır.`);
      reasonRef.current?.focus();
      return;
    }

    setDeciding(true);
    try {
      if (action === 'reject') {
        await api.rejectQuery(request.workspace_id, trimmedReason);
        toast.success('Talep reddedildi', request.username);
      } else {
        await api.approveQuery(request.workspace_id, action === 'approve-share');
        toast.success(
          action === 'approve-share' ? 'Onaylandı ve paylaşıldı' : 'Onaylandı',
          action === 'approve-share'
            ? 'Kullanıcı sorguyu çalıştırıp sonuçları dışa aktarabilir.'
            : 'Sonuçlar kullanıcıyla paylaşılmadı.',
        );
      }
      resetDecisionState();
      onDecided();
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === APPROVAL_CONFLICT) {
        // Another reviewer got there first. The decision is already final on
        // the server, so the list is what is stale here, not the request.
        toast.warning('Bu talep başka bir yönetici tarafından sonuçlandırıldı', 'Liste yenilendi.');
        resetDecisionState();
        onDecided();
        return;
      }
      toast.error('İşlem tamamlanamadı', errorMessage(caught));
    } finally {
      setDeciding(false);
    }
  };

  return (
    <Dialog
      open={request !== null}
      onOpenChange={(open) => {
        if (open) return;
        resetDecisionState();
        onClose();
      }}
      title="Sorgu talebini incele"
      description="Karar verilene kadar kullanıcı bu sorguyu düzenleyemez veya çalıştıramaz."
      size="xl"
      busy={deciding}
      footer={
        <>
          <Button
            variant="danger"
            icon={<ProhibitIcon size={14} />}
            disabled={deciding}
            onClick={() => void decide('reject')}
          >
            Reddet
          </Button>
          <div className="flex-1" />
          <Button icon={<CheckIcon size={14} />} disabled={deciding} onClick={() => void decide('approve')}>
            Onayla, paylaşma
          </Button>
          <Button
            variant="primary"
            icon={<ShareNetworkIcon size={14} />}
            loading={deciding}
            onClick={() => void decide('approve-share')}
          >
            Onayla ve paylaş
          </Button>
        </>
      }
    >
      {request && (
        <div className="flex flex-col gap-5">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-md border border-line bg-sunken px-4 py-3 sm:grid-cols-4">
            {FACTS.map((fact) => (
              <div key={fact.label}>
                <dt className="text-[11.5px] text-subtle">{fact.label}</dt>
                <dd className="mt-0.5 truncate font-mono text-[12.5px] text-fg">{fact.get(request)}</dd>
              </div>
            ))}
            <div>
              <dt className="text-[11.5px] text-subtle">Risk</dt>
              <dd className="mt-0.5">
                {request.risk_type ? (
                  <Badge tone="danger">{request.risk_type}</Badge>
                ) : (
                  <Badge tone="neutral">Sınıflandırılmadı</Badge>
                )}
              </dd>
            </div>
          </dl>

          <section>
            <h3 className="mb-2 text-[12.5px] font-medium text-muted">Gönderilen SQL</h3>
            <div className="h-56 overflow-hidden rounded-md border border-line">
              <CodeEditor value={request.query} readOnly ariaLabel="İncelenen SQL sorgusu" />
            </div>
          </section>

          <section>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-[12.5px] font-medium text-muted">
                Sonuç önizleme
                {previewRows.length > 0 && (
                  <span className="ml-2 font-normal text-subtle">
                    {formatCount(preview?.row_count ?? previewRows.length)} satır
                  </span>
                )}
              </h3>
              <Button size="sm" icon={<EyeIcon size={13} />} loading={previewing} onClick={() => void runPreview()}>
                Önizlemeyi çalıştır
              </Button>
            </div>

            <div className="h-52 overflow-hidden rounded-md border border-line bg-sunken">
              {previewError ? (
                <div className="p-3.5">
                  <pre className="whitespace-pre-wrap break-words rounded-sm border border-danger-line bg-danger-soft p-3 font-mono text-[12px] text-danger">
                    {previewError}
                  </pre>
                </div>
              ) : previewRows.length > 0 ? (
                <DataGrid rows={previewRows} truncated={previewTruncated} className="h-full" />
              ) : preview ? (
                <EmptyState size="sm" title="Sorgu satır döndürmedi" />
              ) : (
                <EmptyState
                  size="sm"
                  title="Önizleme çalıştırılmadı"
                  description="Sorgu hedef veritabanında çalıştırılır ve sonucun ilk satırları burada gösterilir."
                />
              )}
            </div>
          </section>

          <Field
            label="Red gerekçesi"
            hint="Yalnızca reddederken zorunludur. Talebi gönderen kullanıcı ve denetim kaydı bu metni görür."
            error={reasonError ?? undefined}
            aside={
              <span className="font-mono text-[11.5px] text-subtle">
                {reason.trim().length}/{REASON_MAX}
              </span>
            }
          >
            <Textarea
              ref={reasonRef}
              value={reason}
              maxLength={REASON_MAX}
              disabled={deciding}
              placeholder="Örn. Tam tablo güncellemesi, WHERE koşulu olmadan çalıştırılamaz."
              onChange={(event) => {
                setReason(event.target.value);
                if (reasonError) setReasonError(null);
              }}
            />
          </Field>
        </div>
      )}
    </Dialog>
  );
};
