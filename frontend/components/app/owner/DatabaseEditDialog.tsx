import React, { useEffect, useState } from 'react';
import { ApiError, api, errorMessage } from '../../../services/api';
import { CONNECTION_MODE } from '../../../lib/capability';
import type { ConnectionMode, ConnectionModeConflict, RegisteredDatabase } from '../../../types';
import { Badge } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { Dialog } from '../../ui/Dialog';
import { Field } from '../../ui/Field';
import { Input } from '../../ui/Input';
import { SegmentedControl } from '../../ui/SegmentedControl';
import { useToast } from '../../ui/Toast';

const CONNECTION_MODES = (['ro', 'ro_rw', 'ro_rw_ddl'] as const).map((value) => ({
  value,
  label: CONNECTION_MODE[value].label,
}));

const EMPTY = {
  servername: '',
  database_name: '',
  connection_mode: 'ro' as ConnectionMode,
  username_ro: '',
  password_ro: '',
  username_rw: '',
  password_rw: '',
  username_ddl: '',
  password_ddl: '',
};

export interface DatabaseEditDialogProps {
  database: RegisteredDatabase | null;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

/**
 * PATCH the registration: rotate a credential, widen or narrow the mode, or
 * correct a misspelled server/database name (P1-10).
 *
 * Only a field the admin actually edits is sent — WebQuery never returns a
 * stored password, so a full-replacement form would force re-entering every
 * other tier's secret just to rotate one. A blank credential field means
 * "leave this tier alone", not "clear it"; clearing a tier is done by
 * narrowing the connection mode instead, which is why username/password
 * inputs stay disabled for tiers outside the selected mode.
 */
export const DatabaseEditDialog: React.FC<DatabaseEditDialogProps> = ({ database, onOpenChange, onUpdated }) => {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [conflicts, setConflicts] = useState<ConnectionModeConflict[] | null>(null);

  useEffect(() => {
    if (database) {
      setForm({
        ...EMPTY,
        servername: database.servername,
        database_name: database.database_name,
        connection_mode: database.connection_mode ?? 'ro',
      });
      setConflicts(null);
    }
  }, [database]);

  if (!database) return null;

  const identityChanged =
    form.servername.trim() !== database.servername || form.database_name.trim() !== database.database_name;
  const modeChanged = form.connection_mode !== (database.connection_mode ?? 'ro');
  const hasAnyCredentialInput = [
    form.username_ro,
    form.password_ro,
    form.username_rw,
    form.password_rw,
    form.username_ddl,
    form.password_ddl,
  ].some((value) => value.trim());
  const dirty = identityChanged || modeChanged || hasAnyCredentialInput;

  const save = async () => {
    setSaving(true);
    setConflicts(null);
    const payload: Record<string, string> = {};
    if (identityChanged) {
      payload.servername = form.servername.trim();
      payload.database_name = form.database_name.trim();
    }
    if (modeChanged) payload.connection_mode = form.connection_mode;
    for (const tier of ['ro', 'rw', 'ddl'] as const) {
      const username = form[`username_${tier}`].trim();
      const password = form[`password_${tier}`];
      // Username and password travel together: sending one without the other
      // would silently invalidate the pair on the target account.
      if (username || password) {
        payload[`username_${tier}`] = username;
        payload[`password_${tier}`] = password;
      }
    }

    try {
      const result = await api.updateOwnerDatabase(database.id, payload);
      toast.success(
        'Veritabanı kaydı güncellendi',
        result.updated_tiers.length > 0
          ? `Güncellenen kademeler: ${result.updated_tiers.join(', ').toLocaleUpperCase('tr')}`
          : 'Kimlik bilgileri değişti',
      );
      onUpdated();
      onOpenChange(false);
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'CONNECTION_MODE_CONFLICT') {
        setConflicts((caught.context?.conflicts as ConnectionModeConflict[] | undefined) ?? []);
        toast.error('Bağlantı modu daraltılamadı', 'Önce çakışan yetkileri düşürün.');
      } else {
        toast.error('Güncellenemedi', errorMessage(caught));
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={database !== null}
      onOpenChange={onOpenChange}
      title="Veritabanı kaydını güncelle"
      description="Boş bırakılan alanlar değiştirilmez. Bir kademeyi kaldırmak için bağlantı modunu daraltın."
      size="lg"
      busy={saving}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={saving}>
            Vazgeç
          </Button>
          <Button variant="primary" loading={saving} disabled={!dirty} onClick={() => void save()}>
            Kaydet
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
          <Field label="Sunucu adresi">
            <Input
              value={form.servername}
              onChange={(event) => setForm({ ...form, servername: event.target.value })}
              className="font-mono"
            />
          </Field>
          <Field label="Veritabanı adı">
            <Input
              value={form.database_name}
              onChange={(event) => setForm({ ...form, database_name: event.target.value })}
              className="font-mono"
            />
          </Field>
        </div>
        {identityChanged && (
          <p className="text-[12px] text-warning">
            Kimlik değişikliği bu kayda bağlı tüm kayıtlı sorguları yeni ada taşır.
          </p>
        )}

        <Field label="Bağlantı modu" hint="Daraltma, çakışan yetki varsa reddedilir.">
          <SegmentedControl
            value={form.connection_mode}
            onChange={(connection_mode) => setForm({ ...form, connection_mode })}
            segments={CONNECTION_MODES}
            label="Bağlantı modu"
            className="w-full overflow-x-auto"
          />
        </Field>

        {conflicts && conflicts.length > 0 && (
          <div className="rounded-sm border border-danger-line bg-danger-soft p-3">
            <p className="mb-2 text-[12.5px] font-medium text-danger">Çakışan kullanıcı yetkileri</p>
            <ul className="flex flex-col gap-1">
              {conflicts.map((conflict) => (
                <li key={conflict.user_id} className="flex items-center gap-2 text-[12px] text-danger">
                  <span className="font-mono">{conflict.username}</span>
                  <Badge tone="danger" mono>{conflict.role}</Badge>
                  <span>{conflict.unsupported_tier.toLocaleUpperCase('tr')} gerektiriyor</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
          {(['ro', 'rw', 'ddl'] as const).map((tier) => {
            const tierAllowed =
              tier === 'ro' ||
              (tier === 'rw' && form.connection_mode !== 'ro') ||
              (tier === 'ddl' && form.connection_mode === 'ro_rw_ddl');
            return (
              <React.Fragment key={tier}>
                <Field label={`${tier.toLocaleUpperCase('tr')} kullanıcı adı`} hint={tierAllowed ? 'Boş = değiştirme' : 'Bu modda tanımlı değil'}>
                  <Input
                    value={form[`username_${tier}`]}
                    onChange={(event) => setForm({ ...form, [`username_${tier}`]: event.target.value })}
                    disabled={!tierAllowed}
                    autoComplete="off"
                  />
                </Field>
                <Field label={`${tier.toLocaleUpperCase('tr')} şifre`} hint={tierAllowed ? 'Boş = değiştirme' : undefined}>
                  <Input
                    type="password"
                    value={form[`password_${tier}`]}
                    onChange={(event) => setForm({ ...form, [`password_${tier}`]: event.target.value })}
                    disabled={!tierAllowed}
                    autoComplete="new-password"
                  />
                </Field>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </Dialog>
  );
};
