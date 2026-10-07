import React, { useRef, useState } from 'react';
import { CheckIcon, EyeIcon, ProhibitIcon, ShareNetworkIcon } from '@phosphor-icons/react';
import { APPROVAL_CONFLICT, QUERY_CANCELLED, ApiError, api, errorMessage } from '../../../services/api';
import { useQueryCancellation } from '../../../lib/query-cancellation';
import { QueryCancelControl } from '../QueryCancelControl';
import { formatCount } from '../../../lib/format';
import { Badge } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { DataGrid } from '../../ui/DataGrid';
import { Dialog } from '../../ui/Dialog';
import { EmptyState } from '../../ui/EmptyState';
import { Field } from '../../ui/Field';
import { Textarea } from '../../ui/Input';
import { SkeletonRows } from '../../ui/Skeleton';
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
  { label: "Requested by", get: (request) => request.username },
  { label: "Server", get: (request) => request.servername || "Unknown" },
  { label: "Database", get: (request) => request.database },
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
  const [previewCancelled, setPreviewCancelled] = useState(false);
  const cancellation = useQueryCancellation();
  const [deciding, setDeciding] = useState(false);
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState<string | null>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);

  const previewRows = preview?.data ?? [];
  /* The service reports its row cap in the message, not as a flag. */
  const previewTruncated = /truncated/i.test(preview?.message ?? '');

  const runPreview = async () => {
    if (!request) return;
    const executionId = cancellation.begin();
    if (!executionId) return;
    setPreviewing(true);
    setPreviewError(null);
    setPreview(null);
    setPreviewCancelled(false);
    try {
      setPreview(await api.previewQuery(request.workspace_id, executionId));
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === QUERY_CANCELLED) {
        setPreviewCancelled(true);
      } else {
        setPreviewError(errorMessage(caught));
      }
    } finally {
      setPreviewing(false);
      cancellation.finish(executionId);
    }
  };

  const resetDecisionState = () => {
    setPreview(null);
    setPreviewError(null);
    setPreviewCancelled(false);
    setReason('');
    setReasonError(null);
  };

  const decide = async (action: 'reject' | 'approve' | 'approve-share') => {
    if (!request) return;

    const trimmedReason = reason.trim();
    if (action === 'reject' && trimmedReason.length < REASON_MIN) {
      // Caught here rather than at the server so the reviewer keeps what they
      // typed and lands on the field that needs work.
      setReasonError(`The rejection reason must contain at least ${REASON_MIN} characters.`);
      reasonRef.current?.focus();
      return;
    }

    setDeciding(true);
    try {
      if (action === 'reject') {
        await api.rejectQuery(request.workspace_id, trimmedReason);
        toast.success("Request rejected", request.username);
      } else {
        await api.approveQuery(request.workspace_id, action === 'approve-share');
        toast.success(
          action === 'approve-share' ? "Approved and shared" : "Approved",
          action === 'approve-share'
            ? "The user can execute the query and export its results."
            : "Results were not shared with the user.",
        );
      }
      resetDecisionState();
      onDecided();
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === APPROVAL_CONFLICT) {
        // Another reviewer got there first. The decision is already final on
        // the server, so the list is what is stale here, not the request.
        toast.warning("Another administrator has already decided this request", "The list has been refreshed.");
        resetDecisionState();
        onDecided();
        return;
      }
      toast.error("Could not complete the operation", errorMessage(caught));
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
      title="Review query request"
      description="The user cannot edit or run this query until a decision is made."
      size="xl"
      busy={deciding || previewing}
      footer={
        <>
          <Button
            variant="danger"
            icon={<ProhibitIcon size={14} />}
            disabled={deciding || previewing}
            onClick={() => void decide('reject')}
          >
            Reject
          </Button>
          <div className="flex-1" />
          <Button icon={<CheckIcon size={14} />} disabled={deciding || previewing} onClick={() => void decide('approve')}>
            Approve without sharing
          </Button>
          <Button
            variant="primary"
            icon={<ShareNetworkIcon size={14} />}
            loading={deciding}
            disabled={previewing}
            onClick={() => void decide('approve-share')}
          >
            Approve and share
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
                  <Badge tone="neutral">Not classified</Badge>
                )}
              </dd>
            </div>
          </dl>

          <section>
            <h3 className="mb-2 text-[12.5px] font-medium text-muted">Submitted SQL</h3>
            <div className="h-56 overflow-hidden rounded-md border border-line">
              <CodeEditor value={request.query} readOnly ariaLabel="SQL query under review" />
            </div>
          </section>

          <section>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-[12.5px] font-medium text-muted">
                Result preview
                {previewRows.length > 0 && (
                  <span className="ml-2 font-normal text-subtle">
                    {formatCount(preview?.row_count ?? previewRows.length)} rows
                  </span>
                )}
              </h3>
              <div className="flex items-start gap-2">
                <Button
                  size="sm"
                  icon={<EyeIcon size={13} />}
                  disabled={deciding}
                  loading={previewing}
                  onClick={() => void runPreview()}
                >
                  Run preview
                </Button>
                {previewing && <QueryCancelControl cancellation={cancellation} size="sm" />}
              </div>
            </div>

            <div className="h-52 overflow-hidden rounded-md border border-line bg-sunken">
              {previewing ? (
                <div className="p-3.5" role="status" aria-busy="true">
                  <span className="sr-only">Query running</span>
                  <SkeletonRows />
                </div>
              ) : previewCancelled ? (
                <div role="status">
                  <EmptyState size="sm" title="Query cancelled" description="Preview execution stopped on the target database." />
                </div>
              ) : previewError ? (
                <div className="p-3.5">
                  <pre className="whitespace-pre-wrap break-words rounded-sm border border-danger-line bg-danger-soft p-3 font-mono text-[12px] text-danger">
                    {previewError}
                  </pre>
                </div>
              ) : previewRows.length > 0 ? (
                <DataGrid rows={previewRows} truncated={previewTruncated} className="h-full" />
              ) : preview ? (
                <EmptyState size="sm" title="The query returned no rows" />
              ) : (
                <EmptyState
                  size="sm"
                  title="Preview not run yet"
                  description="The query runs on the target database. The first result rows appear here."
                />
              )}
            </div>
          </section>

          <Field
            label="Rejection reason"
            hint="Required only when rejecting. This text is visible to the requester and included in the audit record."
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
              placeholder="For example: A full-table update cannot run without a WHERE clause."
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
