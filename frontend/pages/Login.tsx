import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { EyeIcon, EyeSlashIcon, WarningCircleIcon } from '@phosphor-icons/react';
import { api, errorMessage } from '../services/api';
import { useSession } from '../lib/session';
import { AuthLayout } from '../components/app/AuthLayout';
import { Button, IconButton } from '../components/ui/Button';
import { Field } from '../components/ui/Field';
import { Input } from '../components/ui/Input';

const Login: React.FC = () => {
  const navigate = useNavigate();
  const { refresh } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.login(email, password);
      await refresh();
      navigate('/');
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Sign in to run queries on your registered databases."
      footer={
        <p>
          Don't have an account?{' '}
          <Link to="/register" className="font-medium text-accent underline-offset-4 hover:underline">
            Create an account
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} noValidate={false} className="flex flex-col gap-4">
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-sm border border-danger-line bg-danger-soft px-3 py-2.5 text-[13px] text-danger"
          >
            <WarningCircleIcon size={15} weight="fill" className="mt-px shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <Field label="Email" required>
          <Input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            autoFocus
            required
            placeholder="firstname.lastname@company.com"
          />
        </Field>

        <Field label="Password" required>
          <Input
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
            addon={
              <IconButton
                label={showPassword ? "Hide password" : "Show password"}
                size="sm"
                className="size-6"
                onClick={() => setShowPassword((visible) => !visible)}
              >
                {showPassword ? <EyeSlashIcon size={14} /> : <EyeIcon size={14} />}
              </IconButton>
            }
          />
        </Field>

        <Button type="submit" variant="primary" size="lg" fullWidth loading={submitting} className="mt-1">
          Sign in
        </Button>
      </form>
    </AuthLayout>
  );
};

export default Login;
