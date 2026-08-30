import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircleIcon, EyeIcon, EyeSlashIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { api, errorMessage } from '../services/api';
import { AuthLayout } from '../components/app/AuthLayout';
import { Button, IconButton } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { Input } from '../components/ui/Input';
import { cn } from '../lib/cn';

/** Four independent checks, shown live so the rule is never a surprise. */
function passwordChecks(password: string) {
  return [
    { label: 'En az 12 karakter', ok: password.length >= 12 },
    { label: 'Bir büyük harf', ok: /[A-ZĞÜŞİÖÇ]/.test(password) },
    { label: 'Bir rakam', ok: /\d/.test(password) },
    { label: 'Bir sembol', ok: /[^\p{L}\d]/u.test(password) },
  ];
}

const Register: React.FC = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const checks = useMemo(() => passwordChecks(password), [password]);
  const passwordReady = checks.every((check) => check.ok);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await api.register(username, email, password);
      setDone(true);
      setSuccessMessage(result.message ?? 'Kayıt başvurunuz alındı.');
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title="Hesap oluşturun"
      subtitle="Hesabınız açıldıktan sonra yöneticinizin size veritabanı yetkisi tanımlaması gerekir."
      footer={
        <p>
          Hesabınız var mı?{' '}
          <Link to="/login" className="font-medium text-accent underline-offset-4 hover:underline">
            Oturum açın
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-sm border border-danger-line bg-danger-soft px-3 py-2.5 text-[13px] text-danger"
          >
            <WarningCircleIcon size={15} weight="fill" className="mt-px shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {done && (
          <div
            role="status"
            className="flex items-start gap-2 rounded-sm border border-success-line bg-success-soft px-3 py-2.5 text-[13px] text-success"
          >
            <CheckCircleIcon size={15} weight="fill" className="mt-px shrink-0" />
            <span>{successMessage ?? 'Kayıt başvurunuz alındı.'} Giriş yapmadan önce hesabınızın etkinleştirilmesi gerekebilir.</span>
          </div>
        )}

        <Field label="Kullanıcı adı" required hint="Denetim kayıtlarında bu ad görünür.">
          <Input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            autoFocus
            required
            minLength={3}
            placeholder="ali.donmez"
          />
        </Field>

        <Field label="E-posta" required>
          <Input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
            placeholder="ad.soyad@sirket.com"
          />
        </Field>

        <Field label="Parola" required>
          <Input
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            required
            addon={
              <IconButton
                label={showPassword ? 'Parolayı gizle' : 'Parolayı göster'}
                size="sm"
                className="size-6"
                onClick={() => setShowPassword((visible) => !visible)}
              >
                {showPassword ? <EyeSlashIcon size={14} /> : <EyeIcon size={14} />}
              </IconButton>
            }
          />
        </Field>

        <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          {checks.map((check) => (
            <li
              key={check.label}
              className={cn(
                'flex items-center gap-1.5 text-[12px] transition-colors duration-[var(--dur-fast)]',
                check.ok ? 'text-success' : 'text-subtle',
              )}
            >
              <CheckCircleIcon size={13} weight={check.ok ? 'fill' : 'regular'} className="shrink-0" />
              {check.label}
            </li>
          ))}
        </ul>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          fullWidth
          loading={submitting}
          disabled={!passwordReady || done}
          className="mt-1"
        >
          Hesabı oluştur
        </Button>
      </form>
    </AuthLayout>
  );
};

export default Register;
