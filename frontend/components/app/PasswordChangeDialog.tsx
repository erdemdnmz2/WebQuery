import React, { useState } from 'react';
import { api, errorMessage } from '../../services/api';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { Field } from '../ui/Field';
import { Input } from '../ui/Input';
import { useToast } from '../ui/Toast';

export interface PasswordChangeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Self-service password change (P1-9).
 *
 * There was previously no way to replace a password known to be compromised
 * from inside the application at all — no change endpoint and no reset.
 * `AuditAction.PASSWORD_CHANGED` existed with no call site.
 */
export const PasswordChangeDialog: React.FC<PasswordChangeDialogProps> = ({ open, onOpenChange }) => {
  const toast = useToast();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
  };

  const close = (nextOpen: boolean) => {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  };

  const mismatch = confirmPassword.length > 0 && newPassword !== confirmPassword;
  const canSubmit = currentPassword.length > 0 && newPassword.length >= 12 && newPassword === confirmPassword;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const result = await api.changePassword(currentPassword, newPassword);
      toast.success(
        'Şifreniz güncellendi',
        result.revoked_sessions > 0
          ? `Diğer ${result.revoked_sessions} oturum sonlandırıldı. Bu oturum açık kalır.`
          : 'Bu oturum açık kalır.',
      );
      close(false);
    } catch (caught) {
      toast.error('Şifre değiştirilemedi', errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title="Şifreni değiştir"
      description="Diğer oturumlarınız değişiklikten sonra sonlandırılır; bu oturum açık kalır."
      size="sm"
      busy={submitting}
      footer={
        <>
          <Button variant="ghost" onClick={() => close(false)} disabled={submitting}>
            Vazgeç
          </Button>
          <Button
            type="submit"
            form="password-change-form"
            variant="primary"
            loading={submitting}
            disabled={!canSubmit}
          >
            Şifreyi değiştir
          </Button>
        </>
      }
    >
      <form id="password-change-form" onSubmit={(event) => void submit(event)} className="flex flex-col gap-3.5">
        <Field label="Mevcut şifre" required>
          <Input
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            autoComplete="current-password"
            autoFocus
            required
          />
        </Field>
        <Field label="Yeni şifre" required hint="En az 12 karakter, bir büyük harf ve bir rakam içermeli.">
          <Input
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            autoComplete="new-password"
            required
          />
        </Field>
        <Field label="Yeni şifre (tekrar)" required error={mismatch ? 'Şifreler eşleşmiyor.' : undefined}>
          <Input
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            autoComplete="new-password"
            required
          />
        </Field>
      </form>
    </Dialog>
  );
};
