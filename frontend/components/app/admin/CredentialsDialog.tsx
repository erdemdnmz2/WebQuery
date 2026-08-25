import React, { useState } from 'react';
import { CheckIcon, CopyIcon, EyeIcon, EyeSlashIcon, WarningIcon } from '@phosphor-icons/react';
import { Button, IconButton } from '../../ui/Button';
import { Dialog } from '../../ui/Dialog';
import type { GeneratedCredentials } from '../../../types';

export interface CredentialsDialogProps {
  credentials: GeneratedCredentials | null;
  onClose: () => void;
}

/**
 * Shown once, after a database is registered. The password stays hidden until
 * the reviewer asks for it, so it does not sit exposed on a shared screen.
 */
export const CredentialsDialog: React.FC<CredentialsDialogProps> = ({ credentials, onClose }) => {
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState<'user' | 'password' | null>(null);

  const copy = async (value: string, which: 'user' | 'password') => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(which);
      window.setTimeout(() => setCopied(null), 1600);
    } catch {
      /* Clipboard access can be blocked; the value stays selectable on screen. */
    }
  };

  const close = () => {
    setRevealed(false);
    setCopied(null);
    onClose();
  };

  return (
    <Dialog
      open={credentials !== null}
      onOpenChange={(open) => !open && close()}
      title="Veritabanı erişim bilgileri"
      size="md"
      footer={
        <Button variant="primary" onClick={close}>
          Kaydettim, kapat
        </Button>
      }
    >
      {credentials && (
        <div className="flex flex-col gap-4">
          <div className="flex items-start gap-2.5 rounded-md border border-warning-line bg-warning-soft px-3.5 py-3">
            <WarningIcon size={16} weight="fill" className="mt-px shrink-0 text-warning" />
            <p className="text-[12.5px] leading-relaxed text-warning">
              Parola yalnızca bu ekranda gösterilir ve tekrar görüntülenemez. Kapatmadan önce parola yöneticinize
              kaydedin.
            </p>
          </div>

          <div className="divide-y divide-line rounded-md border border-line">
            <div className="flex items-center gap-3 px-3.5 py-3">
              <span className="w-24 shrink-0 text-[12.5px] text-subtle">Kullanıcı</span>
              <code className="min-w-0 flex-1 select-all truncate font-mono text-[13px] text-fg">
                {credentials.db_username}
              </code>
              <IconButton
                label="Kullanıcı adını kopyala"
                size="sm"
                onClick={() => void copy(credentials.db_username, 'user')}
              >
                {copied === 'user' ? <CheckIcon size={14} className="text-success" /> : <CopyIcon size={14} />}
              </IconButton>
            </div>

            <div className="flex items-center gap-3 px-3.5 py-3">
              <span className="w-24 shrink-0 text-[12.5px] text-subtle">Parola</span>
              <code className="min-w-0 flex-1 select-all truncate font-mono text-[13px] text-fg">
                {revealed ? credentials.db_password : '•'.repeat(Math.min(credentials.db_password.length, 24))}
              </code>
              <IconButton
                label={revealed ? 'Parolayı gizle' : 'Parolayı göster'}
                size="sm"
                onClick={() => setRevealed((visible) => !visible)}
              >
                {revealed ? <EyeSlashIcon size={14} /> : <EyeIcon size={14} />}
              </IconButton>
              <IconButton
                label="Parolayı kopyala"
                size="sm"
                onClick={() => void copy(credentials.db_password, 'password')}
              >
                {copied === 'password' ? <CheckIcon size={14} className="text-success" /> : <CopyIcon size={14} />}
              </IconButton>
            </div>
          </div>
        </div>
      )}
    </Dialog>
  );
};
