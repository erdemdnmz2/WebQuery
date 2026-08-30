import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeftIcon, CompassIcon } from '@phosphor-icons/react';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';

const NotFound: React.FC = () => {
  const navigate = useNavigate();
  return (
    <EmptyState
      className="my-auto"
      icon={<CompassIcon size={18} />}
      title="Bu sayfa yok"
      description="Bağlantı değişmiş veya kayıt silinmiş olabilir. Çalışma alanları listesinden devam edebilirsiniz."
      action={
        <Button variant="primary" icon={<ArrowLeftIcon size={14} />} onClick={() => navigate('/')}>
          Çalışma alanlarına dön
        </Button>
      }
    />
  );
};

export default NotFound;
